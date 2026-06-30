-- Arc G G4 (read-path tenant isolation) — GENERALIZE security_invoker to EVERY public view, not just v_*_truth.
--
-- ★ FOLLOW-ON FINDING (2026-06-21 cross-arc live-push): 20260620000012 fixed the `v_%truth` views, but the
-- LIKE 'v\_%truth' filter MISSED 7 other public views that ALSO ran as their BYPASSRLS owner (postgres) with
-- NO security_invoker, while granted SELECT to anon + authenticated. A non-security_invoker view executes with
-- the VIEW OWNER's privileges and BYPASSES base-table RLS. Three of the 7 read hive-scoped tables with NO hive
-- filter in the view body — a cross-tenant READ LEAK (same class as the truth-view finding), proven by evidence:
--   • v_active_anomaly_alerts → anomaly_alerts  (no WHERE hive_id)  → every hive's alerts
--   • v_sensor_recent        → sensor_readings  (WHERE recorded_at only) → every hive's sensor data
--   • v_audit_unified        → 4 *_audit_log tables → every hive's audit trail
-- (the other 4 — v_conversation_health, v_dialog_state_current, v_industry_standards_coverage,
--  v_session_memory_recent — read RLS tables too; security_invoker makes them respect their own base RLS,
--  which is the correct behavior whether the data is hive-scoped or by-design shared like industry_standards.)
--
-- THE FIX (durable, prevents the next missed view): set security_invoker on ANY public view lacking it, so
-- EVERY view runs as the CALLER and its base-table RLS applies. The base table's RLS — not the view — decides
-- visibility. Idempotent (skips views already set). Verified live two-tenant after apply (see
-- validate_view_security_invoker.py). No view body is rewritten; this only changes the execution security.

do $mig$
declare v record;
begin
  for v in
    select c.relname
    from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'v'
      and (c.reloptions is null or not c.reloptions::text ~* 'security_invoker=(on|true)')
  loop
    execute format('alter view public.%I set (security_invoker = true)', v.relname);
  end loop;
end $mig$;
