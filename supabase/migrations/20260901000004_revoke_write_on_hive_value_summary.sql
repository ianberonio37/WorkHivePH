

--
-- unprotected-write-grant (2026-09-01, board v2 red): v_hive_value_summary (created 20260831000002) is a
-- read-only SUMMARY view, yet it carries INSERT/UPDATE/DELETE for anon AND authenticated. A view cannot own
-- a write; if it is auto-updatable the write lands on the base table with the VIEW OWNER's privileges — an
-- RLS bypass. Its sibling v_community_posts_truth got this exact revoke the same day
-- (20260901000001_revoke_write_on_community_posts_truth_view.sql) and this view was missed — the
-- fix-never-reached-its-sibling class. Revoke-only, additive, no data touched.
REVOKE INSERT, UPDATE, DELETE ON public.v_hive_value_summary FROM anon, authenticated;
