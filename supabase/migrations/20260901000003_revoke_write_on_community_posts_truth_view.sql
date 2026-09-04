-- unprotected-write-grant (2026-09-01): v_community_posts_truth is a read-only TRUTH view, yet it
-- carried INSERT/UPDATE/DELETE for anon AND authenticated. A view cannot own a write; if it is
-- auto-updatable the write lands on the base table (community_posts) with the VIEW OWNER's
-- privileges — an RLS bypass, the exact class the gate exists to catch. Truth views are SELECT-only;
-- every real community_posts write goes through the base table under its own RLS. Precedent:
-- 20260730000002_close_anon_write_on_unprotected_tables.sql. Revoke-only, additive, no data touched.
REVOKE INSERT, UPDATE, DELETE ON public.v_community_posts_truth FROM anon, authenticated;
