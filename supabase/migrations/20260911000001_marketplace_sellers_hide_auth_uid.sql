-- 20260911000001_marketplace_sellers_hide_auth_uid.sql
--
-- FOUND on the J32 founder's-month-end critic walk (W389), proven via PostgREST-as-persona:
-- an ordinary authenticated user (Boyet Ramirez — a solo jeepney rider, no hive, NOT a platform
-- admin) reads EVERY seller's `auth_uid` straight off the base table:
--
--   anon (publishable key, no user token)  -> 42501 permission denied for table marketplace_sellers
--   Boyet's own JWT -> marketplace_sellers?select=worker_name,auth_uid  -> 16 rows, every auth_uid
--
-- `auth_uid` is the internal Supabase identity that RLS itself compares against
-- (`auth_uid = auth.uid()` in mkt_sellers_update / _delete / _insert). The public view
-- `v_marketplace_sellers_truth` was deliberately built to OMIT auth_uid (selecting it from the view
-- returns 42703 column-does-not-exist), which is the design telling us auth_uid is not a public field.
-- But the view is `security_invoker=on`, so it reads the base table AS THE CALLER — and the base table
-- carries a table-level `GRANT SELECT ... TO authenticated`, so a direct base-table read re-exposes the
-- one column the view was careful to hide. hive_id and messenger_username ARE in the view, so they are
-- intended-public and stay readable; only auth_uid is the leak.
--
-- Not an impersonation vector (auth.uid() comes from the signed JWT, which this does not forge), but a
-- cross-tenant identity disclosure: it hands every logged-in user the stable internal id of every
-- seller, correlating each marketplace name to its auth identity across the whole platform.
--
-- FIX — column-level, and it MUST revoke the TABLE grant first. A bare `REVOKE SELECT (auth_uid)` is
-- INERT while a table-wide `GRANT SELECT` stands (the table grant wins — see the column-revoke-inert
-- lesson). So: drop the table-level SELECT for authenticated, then re-grant SELECT on every column
-- EXCEPT auth_uid. The security_invoker view selects only granted columns (it never names auth_uid),
-- so it keeps working; self-scoped writes/filters never needed SELECT on auth_uid (a WHERE filter does
-- not require the column to be SELECT-grantable). anon is untouched — it has no SELECT grant at all.
--
-- RLS is unchanged: mkt_sellers_read stays `auth.uid() IS NOT NULL` because the marketplace legitimately
-- needs authenticated users to browse all sellers' PUBLIC columns through the security_invoker view.
-- The row policy was never the problem; the over-broad COLUMN grant was.

BEGIN;

REVOKE SELECT ON public.marketplace_sellers FROM authenticated;

GRANT SELECT (
  id, worker_name, hive_id, tier,
  kyb_verified, kyb_verified_at,
  cert_verified, cert_verified_at, certifications,
  total_sales, rating_avg, rating_count,
  response_rate, response_time_h,
  messenger_username,
  created_at, updated_at
) ON public.marketplace_sellers TO authenticated;

COMMIT;
