-- get_hive_board_dashboard(hive_id) — fan-out collapse for the Hive Board (hive.html).
-- ============================================================================
-- hive.html initBoard() fans out to ~37 PostgREST reads across 16 loaders.
-- This RPC (PHASE 1) collapses the 5 pure HIVE-SCOPED plain-read loaders into a
-- single jsonb round-trip:
--   loadMembers       -> members + open_jobs_workers
--   loadFeed          -> feed_logbook + open_count + feed_pm
--   loadPMHealth      -> pm_scope
--   checkTeamStockAlert -> team_inventory
--   loadApprovalQueue -> pending_assets + pending_parts
--
-- Worker-scoped loaders (checkStockAlert, buildNotifications) and the analytics
-- cards (audit, brief, patterns, benchmarks, pulse) + the write-side
-- readiness/adoption snapshots are Phase 2/3 — NOT in this RPC. Each rewired
-- loader keeps RPC-first + legacy fallback, so partial coverage is safe.
--
-- PARITY-SAFE: every sub-select reads the SAME canonical view/table with the
-- same filters the client used, so output is identical by construction.
-- Proven by tests/journey-hive-board-parity.spec.ts.
--
-- HIVE ISOLATION (critical): SECURITY DEFINER bypasses RLS, so this verifies
-- the caller is an active member of p_hive_id via auth.uid() before any read.
-- canonical-allow: read-optimization transport that bundles already-canonical
-- v_*_truth + hive-scoped signals into one round-trip; NOT a new canonical
-- source, so anchored here rather than registered in canonical_sources.

BEGIN;

-- canonical-allow: read-optimization transport bundling already-canonical
-- v_*_truth + hive-scoped signals into one round-trip; NOT a new canonical
-- source, so anchored here rather than registered in canonical_sources.
CREATE OR REPLACE FUNCTION public.get_hive_board_dashboard(
  p_hive_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_is_member boolean;
  v_result    jsonb;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM public.hive_members
    WHERE hive_id  = p_hive_id
      AND auth_uid = auth.uid()
      AND status   = 'active'
  ) INTO v_is_member;

  IF NOT v_is_member THEN
    RAISE EXCEPTION
      'get_hive_board_dashboard: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;

  SELECT jsonb_build_object(

    -- loadMembers: hive_members (non-kicked, joined order) + open-jobs worker list
    'members', COALESCE((
      SELECT jsonb_agg(m) FROM (
        SELECT worker_name, role, status
        FROM public.hive_members
        WHERE hive_id = p_hive_id AND status <> 'kicked'
        ORDER BY joined_at
      ) m
    ), '[]'::jsonb),
    'open_jobs_workers', COALESCE((
      SELECT jsonb_agg(w) FROM (
        SELECT worker_name
        FROM public.v_logbook_truth
        WHERE hive_id = p_hive_id AND status = 'Open'
      ) w
    ), '[]'::jsonb),

    -- loadFeed: recent logbook (limit 40) + exact open count + recent PM (limit 20)
    'feed_logbook', COALESCE((
      SELECT jsonb_agg(l) FROM (
        SELECT id, worker_name, date, machine, category, problem, status, created_at
        FROM public.v_logbook_truth
        WHERE hive_id = p_hive_id
        ORDER BY created_at DESC NULLS LAST
        LIMIT 40
      ) l
    ), '[]'::jsonb),
    'open_count', (
      SELECT count(*) FROM public.v_logbook_truth
      WHERE hive_id = p_hive_id AND status = 'Open'
    ),
    'feed_pm', COALESCE((
      SELECT jsonb_agg(p) FROM (
        SELECT pc.id, pc.worker_name, pc.asset_id, pc.scope_item_id,
               pc.status, pc.completed_at,
               pa.asset_name           AS asset_name,
               psi.item_text           AS item_text,
               psi.frequency           AS frequency
        FROM public.pm_completions pc
        LEFT JOIN public.pm_assets       pa  ON pa.id  = pc.asset_id
        LEFT JOIN public.pm_scope_items  psi ON psi.id = pc.scope_item_id
        WHERE pc.hive_id = p_hive_id AND pc.status = 'done'
        ORDER BY pc.completed_at DESC NULLS LAST
        LIMIT 20
      ) p
    ), '[]'::jsonb),

    -- loadPMHealth: per-scope-item overdue/due-soon flags (counts derived client-side)
    'pm_scope', COALESCE((
      SELECT jsonb_agg(s) FROM (
        SELECT scope_item_id, pm_asset_id, asset_name, is_overdue, is_due_soon
        FROM public.v_pm_scope_items_truth
        WHERE hive_id = p_hive_id
      ) s
    ), '[]'::jsonb),

    -- checkTeamStockAlert: hive approved inventory (client filters self + low/out)
    'team_inventory', COALESCE((
      SELECT jsonb_agg(i) FROM (
        SELECT worker_name, part_name, qty_on_hand, min_qty
        FROM public.v_inventory_items_truth
        WHERE hive_id = p_hive_id AND status = 'approved'
      ) i
    ), '[]'::jsonb),

    -- loadApprovalQueue: pending assets + pending parts (supervisor-gated client-side)
    'pending_assets', COALESCE((
      SELECT jsonb_agg(a) FROM (
        SELECT id, tag AS asset_id, name, iso_class AS type, location,
               criticality, hive_id, worker_name, status, submitted_by, created_at
        FROM public.asset_nodes
        WHERE hive_id = p_hive_id AND status = 'pending'
      ) a
    ), '[]'::jsonb),
    'pending_parts', COALESCE((
      SELECT jsonb_agg(p) FROM (
        SELECT id, part_number, part_name, qty_on_hand, category,
               submitted_by, worker_name, status
        FROM public.v_inventory_items_truth
        WHERE hive_id = p_hive_id AND status = 'pending'
      ) p
    ), '[]'::jsonb)

  ) INTO v_result;

  RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.get_hive_board_dashboard(uuid) IS
  'Hive Board (hive.html) fan-out collapse PHASE 1: members/feed/pm-health/team-stock/approval-queue in one jsonb round-trip. Membership-gated via auth.uid() (SECURITY DEFINER bypasses RLS). Reads the same canonical views/tables as the client loaders so output is parity-equal. Worker-scoped + analytics + readiness/adoption loaders remain on their own queries (Phase 2/3).';

GRANT EXECUTE ON FUNCTION public.get_hive_board_dashboard(uuid) TO authenticated;

COMMIT;
