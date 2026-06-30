-- D3.3 (INTERACTIVE_LINEAGE_ROADMAP) — publish the two tables that back the
-- last realtime gaps so their live feeds actually fan out:
--   * asset_risk_scores — backs v_risk_truth (predictive.html). The nightly batch
--     risk-scoring job AND asset-hub FMEA edits (→ risk composite recompute) write
--     here; an open predictive page should refresh its risk ranking live.
--   * schedule_items — the personal day plan (dayplanner.html). An edit on one
--     device should reflect on the same worker's other open sessions.
--
-- SAFETY (realtime-engineer skill, Arc J — publishing an RLS-off / anon-permissive
-- table is a cross-tenant exfiltration feed): both are RLS-enabled with NO anon
-- bypass — verified via pg_policies 2026-06-29:
--   asset_risk_scores: ALL  USING (auth.uid() IS NOT NULL AND hive_id IN user_hive_ids())  [hive-scoped]
--   schedule_items:    SELECT USING (auth.uid() IS NOT NULL AND auth_uid = auth.uid())     [owner-scoped]
-- An anon read (auth.uid() IS NULL) returns 0 rows from both. The realtime
-- subscription-isolation gate keeps them locked.
--
-- REPLICA IDENTITY FULL so a DELETE event carries the full old row (incl. the
-- filter column — hive_id / worker_name) — required for the client filter to
-- match on DELETE (e.g. removing a planned schedule item).
--
-- Idempotent: guard each ADD with a membership check (ADD errors if already a member).

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['asset_risk_scores', 'schedule_items'] LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_publication_tables
      WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = t
    ) THEN
      EXECUTE format('ALTER PUBLICATION supabase_realtime ADD TABLE public.%I', t);
    END IF;
    EXECUTE format('ALTER TABLE public.%I REPLICA IDENTITY FULL', t);
  END LOOP;
END $$;
