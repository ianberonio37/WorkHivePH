-- get_hive_board_dashboard — PHASE 3: + worker-scoped own data + readiness/adoption.
-- ============================================================================
-- Supersedes 20260607000001 (CREATE OR REPLACE). Adds:
--   checkStockAlert / buildNotifications -> own_inventory + own_old_wos
--   loadMaturityStairway                 -> readiness  (composes get_hive_readiness_current)
--   loadAdoptionCard                     -> adoption   (composes get_adoption_risk_current)
-- loadTeamPulse reuses the existing team_inventory key for its stock-issues
-- count (client-side), so no new key is needed for that.
--
-- WORKER SCOPE (critical): the caller's display_name is derived from auth.uid()
-- via worker_profiles INSIDE the function — NEVER from a passed param — so a
-- caller can only ever read their OWN worker-scoped rows (no cross-user leak).
--
-- readiness/adoption: the loaders keep their compute-if-stale + realtime
-- re-subscribe; this RPC only supplies the INITIAL get_*_current snapshot so
-- the board's first paint skips those reads. Each compose is wrapped so a
-- failure in a sub-RPC degrades to null instead of aborting the whole payload.
--
-- canonical-allow placed adjacent to CREATE (must be within 4 lines).

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
  v_role      text;
  v_is_sup    boolean;
  v_caller    text;
  v_readiness jsonb;
  v_adoption  jsonb;
  v_result    jsonb;
BEGIN
  SELECT role INTO v_role
  FROM public.hive_members
  WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active';

  IF v_role IS NULL THEN
    RAISE EXCEPTION
      'get_hive_board_dashboard: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;
  v_is_sup := (v_role = 'supervisor');

  -- Caller identity for worker-scoped reads (spoof-proof: from the JWT, not a param).
  SELECT display_name INTO v_caller FROM public.worker_profiles WHERE auth_uid = auth.uid();

  -- Readiness/adoption snapshots — compose existing RPCs, degrade to null on error.
  BEGIN
    SELECT to_jsonb(r) INTO v_readiness FROM public.get_hive_readiness_current(p_hive_id) r LIMIT 1;
  EXCEPTION WHEN OTHERS THEN v_readiness := NULL;
  END;
  BEGIN
    SELECT to_jsonb(a) INTO v_adoption FROM public.get_adoption_risk_current(p_hive_id) a LIMIT 1;
  EXCEPTION WHEN OTHERS THEN v_adoption := NULL;
  END;

  SELECT jsonb_build_object(

    -- ── All members ──────────────────────────────────────────────────
    'members', COALESCE((SELECT jsonb_agg(m) FROM (
        SELECT worker_name, role, status FROM public.hive_members
        WHERE hive_id = p_hive_id AND status <> 'kicked' ORDER BY joined_at) m), '[]'::jsonb),
    'open_jobs_workers', COALESCE((SELECT jsonb_agg(w) FROM (
        SELECT worker_name FROM public.v_logbook_truth
        WHERE hive_id = p_hive_id AND status = 'Open') w), '[]'::jsonb),
    'feed_logbook', COALESCE((SELECT jsonb_agg(l) FROM (
        SELECT id, worker_name, date, machine, category, problem, status, created_at
        FROM public.v_logbook_truth WHERE hive_id = p_hive_id
        ORDER BY created_at DESC NULLS LAST LIMIT 40) l), '[]'::jsonb),
    'open_count', (SELECT count(*) FROM public.v_logbook_truth
        WHERE hive_id = p_hive_id AND status = 'Open'),
    'feed_pm', COALESCE((SELECT jsonb_agg(p) FROM (
        SELECT pc.id, pc.worker_name, pc.asset_id, pc.scope_item_id, pc.status,
               pc.completed_at, pa.asset_name, psi.item_text, psi.frequency
        FROM public.pm_completions pc
        LEFT JOIN public.pm_assets      pa  ON pa.id  = pc.asset_id
        LEFT JOIN public.pm_scope_items psi ON psi.id = pc.scope_item_id
        WHERE pc.hive_id = p_hive_id AND pc.status = 'done'
        ORDER BY pc.completed_at DESC NULLS LAST LIMIT 20) p), '[]'::jsonb),
    'pm_scope', COALESCE((SELECT jsonb_agg(s) FROM (
        SELECT scope_item_id, pm_asset_id, asset_name, is_overdue, is_due_soon
        FROM public.v_pm_scope_items_truth WHERE hive_id = p_hive_id) s), '[]'::jsonb),

    -- ── Worker-scoped (caller's own; derived identity) ───────────────
    'own_inventory', COALESCE((SELECT jsonb_agg(i) FROM (
        SELECT part_name, qty_on_hand, min_qty FROM public.v_inventory_items_truth
        WHERE worker_name = v_caller AND status = 'approved') i), '[]'::jsonb),
    'own_old_wos', COALESCE((SELECT jsonb_agg(w) FROM (
        SELECT machine, date, created_at FROM public.v_logbook_truth
        WHERE worker_name = v_caller AND status = 'Open'
          AND created_at < (now() - interval '48 hours')
          AND (hive_id = p_hive_id OR hive_id IS NULL)
        ORDER BY created_at DESC LIMIT 5) w), '[]'::jsonb),

    -- ── Analytics cards (all members) ────────────────────────────────
    'ai_reports', jsonb_build_object(
      'failure_digest', (SELECT to_jsonb(x) FROM (SELECT summary, report_json, generated_at, report_type
        FROM public.v_ai_reports_truth WHERE hive_id = p_hive_id AND report_type = 'failure_digest'
        ORDER BY generated_at DESC LIMIT 1) x),
      'predictive', (SELECT to_jsonb(x) FROM (SELECT summary, report_json, generated_at, report_type
        FROM public.v_ai_reports_truth WHERE hive_id = p_hive_id AND report_type = 'predictive'
        ORDER BY generated_at DESC LIMIT 1) x),
      'pm_overdue', (SELECT to_jsonb(x) FROM (SELECT summary, report_json, generated_at, report_type
        FROM public.v_ai_reports_truth WHERE hive_id = p_hive_id AND report_type = 'pm_overdue'
        ORDER BY generated_at DESC LIMIT 1) x)),
    'pattern_alerts', COALESCE((SELECT jsonb_agg(a) FROM (
        SELECT machine, category, title, detail, severity, rule_id, detected_at
        FROM public.v_alert_truth
        WHERE hive_id = p_hive_id AND alert_kind = 'signature' AND status = 'active'
        ORDER BY severity DESC, detected_at DESC LIMIT 5) a), '[]'::jsonb),
    'benchmarks', jsonb_build_object(
      'hive', COALESCE((SELECT jsonb_agg(h) FROM (SELECT equipment_category, mtbf_days, failure_count, sample_machines
        FROM public.hive_benchmarks WHERE hive_id = p_hive_id ORDER BY failure_count DESC LIMIT 5) h), '[]'::jsonb),
      'network', COALESCE((SELECT jsonb_agg(n) FROM (SELECT equipment_category, avg_mtbf_days, p75_mtbf_days, sample_hives
        FROM public.network_benchmarks ORDER BY sample_hives DESC LIMIT 10) n), '[]'::jsonb)),

    -- ── Readiness + adoption snapshots (initial read only) ───────────
    'readiness', v_readiness,
    'adoption',  CASE WHEN v_is_sup THEN v_adoption ELSE NULL END,

    -- ── Supervisor-only keys (NULL for non-supervisors) ──────────────
    'team_inventory', CASE WHEN v_is_sup THEN COALESCE((SELECT jsonb_agg(i) FROM (
        SELECT worker_name, part_name, qty_on_hand, min_qty FROM public.v_inventory_items_truth
        WHERE hive_id = p_hive_id AND status = 'approved') i), '[]'::jsonb) ELSE NULL END,
    'pending_assets', CASE WHEN v_is_sup THEN COALESCE((SELECT jsonb_agg(a) FROM (
        SELECT id, tag AS asset_id, name, iso_class AS type, location, criticality,
               hive_id, worker_name, status, submitted_by, created_at
        FROM public.asset_nodes WHERE hive_id = p_hive_id AND status = 'pending') a), '[]'::jsonb) ELSE NULL END,
    'pending_parts', CASE WHEN v_is_sup THEN COALESCE((SELECT jsonb_agg(p) FROM (
        SELECT id, part_number, part_name, qty_on_hand, category, submitted_by, worker_name, status
        FROM public.v_inventory_items_truth WHERE hive_id = p_hive_id AND status = 'pending') p), '[]'::jsonb) ELSE NULL END,
    'audit_log', CASE WHEN v_is_sup THEN COALESCE((SELECT jsonb_agg(a) FROM (
        SELECT id, action, actor, target_name, target_type, target_id, meta, created_at
        FROM public.hive_audit_log WHERE hive_id = p_hive_id
        ORDER BY created_at DESC LIMIT 50) a), '[]'::jsonb) ELSE NULL END

  ) INTO v_result;

  RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.get_hive_board_dashboard(uuid) IS
  'Hive Board (hive.html) fan-out collapse PHASE 3: members/feed/pm/analytics (P1+P2) + worker-scoped own_inventory/own_old_wos (caller derived from auth.uid()) + readiness/adoption snapshots (composes get_*_current; loaders keep compute-if-stale + realtime). Membership-gated; supervisor-only keys NULL for non-supervisors. Parity-equal to the client loaders by construction.';

GRANT EXECUTE ON FUNCTION public.get_hive_board_dashboard(uuid) TO authenticated;

COMMIT;
