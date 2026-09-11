-- write_authz_depth (founder-console, P-B P80, 2026-09-05): the console's two direct writes - marketplace_sellers
-- (verify a seller) and service_vouchers (campaign edits) - must be refused in the DATABASE for a signed-in
-- user who is neither the row's owner nor a marketplace admin. mkt_sellers_update carries
-- USING/WITH CHECK (auth_uid = auth.uid() OR is_marketplace_admin()); a USING clause FILTERS, so the probe
-- counts touched rows: a non-admin member updating another seller's row touches 0, and the row is unchanged.
-- expect: fixture_nonadmin_and_foreign_seller \| t
-- expect: foreign_seller_update_touched \| 0
-- expect: foreign_voucher_update_touched \| 0
-- expect: rows_unchanged_after_rollback \| t
CREATE TEMP TABLE _wa AS
SELECT (SELECT m.auth_uid FROM hive_members m JOIN worker_profiles wp ON wp.auth_uid = m.auth_uid
         WHERE m.status = 'active' AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.worker_name = wp.display_name)
           AND NOT EXISTS (SELECT 1 FROM marketplace_sellers s WHERE s.auth_uid = m.auth_uid) LIMIT 1) AS me,
       (SELECT s.id FROM marketplace_sellers s WHERE s.auth_uid IS NOT NULL LIMIT 1) AS seller,
       (SELECT v.id FROM service_vouchers v LIMIT 1) AS voucher,
       (SELECT md5(string_agg(s.id::text || coalesce(s.kyb_verified::text,''), ',' ORDER BY s.id)) FROM marketplace_sellers s) AS sellers_sig,
       (SELECT count(*) FROM service_vouchers) AS n_vouchers;
GRANT SELECT ON _wa TO authenticated;
SELECT 'fixture_nonadmin_and_foreign_seller | ' || ((SELECT me FROM _wa) IS NOT NULL AND (SELECT seller FROM _wa) IS NOT NULL AND (SELECT voucher FROM _wa) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wa)::text, 'role','authenticated')::text, true);
WITH u AS (UPDATE marketplace_sellers SET kyb_verified = NOT coalesce(kyb_verified, false) WHERE id = (SELECT seller FROM _wa) RETURNING 1)
SELECT 'foreign_seller_update_touched | ' || count(*) FROM u;
WITH v AS (UPDATE service_vouchers SET id = id WHERE id = (SELECT voucher FROM _wa) RETURNING 1)   -- a no-op SET (id = id): only the policy decides whether a row is touched
SELECT 'foreign_voucher_update_touched | ' || count(*) FROM v;
ROLLBACK;
SELECT 'rows_unchanged_after_rollback | ' || ((SELECT md5(string_agg(s.id::text || coalesce(s.kyb_verified::text,''), ',' ORDER BY s.id)) FROM marketplace_sellers s) = (SELECT sellers_sig FROM _wa) AND (SELECT count(*) FROM service_vouchers) = (SELECT n_vouchers FROM _wa));
