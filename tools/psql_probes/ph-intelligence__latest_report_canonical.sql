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
-- before the report was generated (intelligence-report/index.ts:66-74) - not the platform's hive total.
SELECT 'hive_count_agrees | ' || (
  (SELECT hive_count FROM _latest) = (
    SELECT count(DISTINCT hive_id) FROM v_logbook_truth
    WHERE hive_id IS NOT NULL
      AND created_at >= (SELECT generated_at FROM _latest) - interval '90 days'
      AND created_at <= (SELECT generated_at FROM _latest)));
