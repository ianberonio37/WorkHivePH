-- get_hive_board_dashboard — PHASE 2: + analytics cards + in-RPC role gating.
-- ============================================================================
-- Supersedes 20260607000000 (CREATE OR REPLACE). Adds the supervisor/analytics
-- read-only cards to the board collapse:
--   loadAuditLog     -> audit_log          (SUPERVISOR-only)
--   loadTodaysBrief  -> ai_reports         (latest per report_type)
--   loadPatternAlerts-> pattern_alerts     (v_alert_truth signature, active)
--   loadBenchmarks   -> benchmarks {hive, network}
--
-- SECURITY UPGRADE: Phase 1 returned supervisor-only data (approvals,
-- team-stock) to any member (UI-gated only). This version derives the caller's
-- role from hive_members and NULLs the supervisor-only keys for non-supervisors
-- (audit_log, pending_assets, pending_parts, team_inventory) — defense in depth
-- matching the UI gate. The loaders already early-return for non-supervisors,
-- so this changes no rendered behavior, only what's on the wire.
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
  v_role   text;
  v_is_sup boolean;
  v_result jsonb;
BEGIN
  -- Membership gate + role lookup in one shot.
  SELECT role INTO v_role
  FROM public.hive_members
  WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active';

  IF v_role IS NULL THEN
    RAISE EXCEPTION
      'get_hive_board_dashboard: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;
  v_is_sup := (v_role = 'supervisor');

  SELECT jsonb_build_object(

    -- ── All members ──────────────────────────────────────────────────
    'members', COALESCE((
      SELECT jsonb_agg(m) FROM (
        SELECT worker_name, role, status FROM public.hive_members
        WHERE hive_id = p_hive_id AND status <> 'kicked' ORDER BY joined_at
      ) m), '[]'::jsonb),
    'open_jobs_workers', COALESCE((
      SELECT jsonb_agg(w) FROM (
        SELECT worker_name FROM public.v_logbook_truth
        WHERE hive_id = p_hive_id AND status = 'Open'
      ) w), '[]'::jsonb),
    'feed_logbook', COALESCE((
      SELECT jsonb_agg(l) FROM (
        SELECT id, worker_name, date, machine, category, problem, status, created_at
        FROM public.v_logbook_truth WHERE hive_id = p_hive_id
        ORDER BY created_at DESC NULLS LAST LIMIT 40
      ) l), '[]'::jsonb),
    'open_count', (
      SELECT count(*) FROM public.v_logbook_truth
      WHERE hive_id = p_hive_id AND status = 'Open'),
    'feed_pm', COALESCE((
      SELECT jsonb_agg(p) FROM (
        SELECT pc.id, pc.worker_name, pc.asset_id, pc.scope_item_id, pc.status,
               pc.completed_at, pa.asset_name, psi.item_text, psi.frequency
        FROM public.pm_completions pc
        LEFT JOIN public.pm_assets      pa  ON pa.id  = pc.asset_id
        LEFT JOIN public.pm_scope_items psi ON psi.id = pc.scope_item_id
        WHERE pc.hive_id = p_hive_id AND pc.status = 'done'
        ORDER BY pc.completed_at DESC NULLS LAST LIMIT 20
      ) p), '[]'::jsonb),
    'pm_scope', COALESCE((
      SELECT jsonb_agg(s) FROM (
        SELECT scope_item_id, pm_asset_id, asset_name, is_overdue, is_due_soon
        FROM public.v_pm_scope_items_truth WHERE hive_id = p_hive_id
      ) s), '[]'::jsonb),

    -- ── Analytics cards (all members) ────────────────────────────────
    -- loadTodaysBrief: latest report per type
    'ai_reports', jsonb_build_object(
      'failure_digest', (SELECT to_jsonb(x) FROM (
        SELECT summary, report_json, generated_at, report_type FROM public.v_ai_reports_truth
        WHERE hive_id = p_hive_id AND report_type = 'failure_digest'
        ORDER BY generated_at DESC LIMIT 1) x),
      'predictive', (SELECT to_jsonb(x) FROM (
        SELECT summary, report_json, generated_at, report_type FROM public.v_ai_reports_truth
        WHERE hive_id = p_hive_id AND report_type = 'predictive'
        ORDER BY generated_at DESC LIMIT 1) x),
      'pm_overdue', (SELECT to_jsonb(x) FROM (
        SELECT summary, report_json, generated_at, report_type FROM public.v_ai_reports_truth
        WHERE hive_id = p_hive_id AND report_type = 'pm_overdue'
        ORDER BY generated_at DESC LIMIT 1) x)
    ),
    -- loadPatternAlerts: signature alerts, active
    'pattern_alerts', COALESCE((
      SELECT jsonb_agg(a) FROM (
        SELECT machine, category, title, detail, severity, rule_id, detected_at
        FROM public.v_alert_truth
        WHERE hive_id = p_hive_id AND alert_kind = 'signature' AND status = 'active'
        ORDER BY severity DESC, detected_at DESC LIMIT 5
      ) a), '[]'::jsonb),
    -- loadBenchmarks: this hive's metrics + the network aggregate
    'benchmarks', jsonb_build_object(
      'hive', COALESCE((SELECT jsonb_agg(h) FROM (
        SELECT equipment_category, mtbf_days, failure_count, sample_machines
        FROM public.hive_benchmarks WHERE hive_id = p_hive_id
        ORDER BY failure_count DESC LIMIT 5) h), '[]'::jsonb),
      'network', COALESCE((SELECT jsonb_agg(n) FROM (
        SELECT equipment_category, avg_mtbf_days, p75_mtbf_days, sample_hives
        FROM public.network_benchmarks
        ORDER BY sample_hives DESC LIMIT 10) n), '[]'::jsonb)
    ),

    -- ── Supervisor-only keys (NULL for non-supervisors) ──────────────
    'team_inventory', CASE WHEN v_is_sup THEN COALESCE((
      SELECT jsonb_agg(i) FROM (
        SELECT worker_name, part_name, qty_on_hand, min_qty
        FROM public.v_inventory_items_truth
        WHERE hive_id = p_hive_id AND status = 'approved'
      ) i), '[]'::jsonb) ELSE NULL END,
    'pending_assets', CASE WHEN v_is_sup THEN COALESCE((
      SELECT jsonb_agg(a) FROM (
        SELECT id, tag AS asset_id, name, iso_class AS type, location, criticality,
               hive_id, worker_name, status, submitted_by, created_at
        FROM public.asset_nodes WHERE hive_id = p_hive_id AND status = 'pending'
      ) a), '[]'::jsonb) ELSE NULL END,
    'pending_parts', CASE WHEN v_is_sup THEN COALESCE((
      SELECT jsonb_agg(p) FROM (
        SELECT id, part_number, part_name, qty_on_hand, category, submitted_by, worker_name, status
        FROM public.v_inventory_items_truth WHERE hive_id = p_hive_id AND status = 'pending'
      ) p), '[]'::jsonb) ELSE NULL END,
    'audit_log', CASE WHEN v_is_sup THEN COALESCE((
      SELECT jsonb_agg(a) FROM (
        SELECT id, action, actor, target_name, target_type, target_id, meta, created_at
        FROM public.hive_audit_log WHERE hive_id = p_hive_id
        ORDER BY created_at DESC LIMIT 50
      ) a), '[]'::jsonb) ELSE NULL END

  ) INTO v_result;

  RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.get_hive_board_dashboard(uuid) IS
  'Hive Board (hive.html) fan-out collapse PHASE 2: members/feed/pm/team-stock/approvals (P1) + audit-log/ai-brief/pattern-alerts/benchmarks (P2) in one jsonb round-trip. Membership-gated via auth.uid(); supervisor-only keys (audit_log, pending_*, team_inventory) are NULL for non-supervisors. Reads the same canonical views/tables as the client loaders so output is parity-equal. Worker-scoped (stock/notif) + readiness/adoption remain on their own queries (Phase 3).';

GRANT EXECUTE ON FUNCTION public.get_hive_board_dashboard(uuid) TO authenticated;

COMMIT;
