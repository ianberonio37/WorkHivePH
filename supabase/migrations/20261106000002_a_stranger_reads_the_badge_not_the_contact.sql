-- ★A STRANGER READ A SELLER'S CONTACT FROM THE TABLE THE VIEW MASKS IT IN (2026-11-06, GJ M9 J31 hand-off 2).
--
-- The design is written in 20260907000006 (sellers_public_view): a stranger reads a seller through a view that carries
-- the BADGE and not the CONTACT - messenger_username, certifications and the verification and join dates are masked to
-- NULL for a visitor without an account, and the page then says "sign in to contact". 20260803000027 had narrowed anon
-- to the badge columns with a column grant, so the table agreed with the view.
--
-- 20261006000001 then closed a real leak (anon could read auth_uid) by dropping the table grant and granting back
-- "the live schema minus auth_uid" - every other column, the masked ones included. So the view still answered NULL and
-- the table under it answered the contact: a stranger asking marketplace_sellers directly through the API read
-- messenger_username, certifications, kyb_verified_at, cert_verified_at and created_at for every seller with a published
-- listing (policy mkt_sellers_read_anon). Measured as anon in one rolled-back transaction: the view read NULL, the table
-- read the contact.
--
-- Anon keeps the ROWS (a public marketplace shows who is selling) and keeps exactly the columns a stranger's own reads
-- need: v_marketplace_listings_public is security_invoker and joins this table on worker_name for the eight badge and
-- rating columns. Everything else a stranger sees of a seller comes through v_marketplace_sellers_public and the
-- seller RPCs, which run as their owner and are untouched. A column added later stays closed to anon, as before.

BEGIN;

REVOKE SELECT ON public.marketplace_sellers FROM anon;
-- a table-level revoke also takes the column grants; said explicitly so the intent survives a reader who doubts it
REVOKE SELECT (id, hive_id, messenger_username, certifications, kyb_verified_at, cert_verified_at, created_at, updated_at)
  ON public.marketplace_sellers FROM anon;

GRANT SELECT (worker_name, tier, kyb_verified, cert_verified, total_sales, rating_avg, rating_count, response_rate, response_time_h)
  ON public.marketplace_sellers TO anon;

COMMIT;
