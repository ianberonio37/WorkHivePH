-- latest_report_canonical (P-C tile == DB canonical, 2026-09-05): ph-intelligence paints the LATEST
-- ph_intelligence_reports row — its summary / mtbf_rankings / failure_modes and the hive/WO/equipment
-- counts. The canonical for this page IS that row: it must exist, be recent, carry the three sections
-- the page renders, and its hive_count must equal the hives the platform actually has. The deeper
-- truth (report vs its source tables) is the intelligence-report function's own contract gates.
-- expect: latest_exists \| t
-- expect: latest_is_recent \| t
-- expect: sections_present \| t
-- expect: hive_count_agrees \| t
CREATE TEMP TABLE _latest AS
SELECT * FROM ph_intelligence_reports ORDER BY generated_at DESC LIMIT 1;
SELECT 'latest_exists | ' || ((SELECT count(*) FROM _latest) = 1);
SELECT 'latest_is_recent | ' || ((SELECT generated_at FROM _latest) > now() - interval '60 days');
SELECT 'sections_present | ' || (
  (SELECT report_json ? 'summary' AND report_json ? 'mtbf_rankings' AND report_json ? 'failure_modes' FROM _latest));
-- hive_count is the function's active_hives: DISTINCT hive_id in v_logbook_truth within the 90 days
-- before the report was generated (intelligence-report/index.ts gatherData) - not the platform's hive total.
-- 2026-10-08: only CONSENTING hives count (hives.federated_benchmark_opted_in, _shared/federated-consent.ts), and
-- below MIN_CONSENTING_HIVES the report publishes nothing cross-hive (insufficient_consent, hive_count 0). The old
-- rule counted every hive - which is how a synthetic eval hive created a day later turned this probe red.
SELECT 'hive_count_agrees | ' || (
  (SELECT hive_count FROM _latest) = CASE
    WHEN (SELECT (report_json->'summary'->>'insufficient_consent')::boolean FROM _latest) THEN 0
    ELSE (SELECT count(DISTINCT v.hive_id) FROM v_logbook_truth v
           JOIN public.hives h ON h.id = v.hive_id AND h.federated_benchmark_opted_in
          WHERE v.created_at >= (SELECT generated_at FROM _latest) - interval '90 days'
            AND v.created_at <= (SELECT generated_at FROM _latest))
  END);
