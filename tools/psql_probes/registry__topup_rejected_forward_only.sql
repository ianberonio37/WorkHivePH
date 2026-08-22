-- money-lifecycle topup-rejected: a REJECTED top-up minted nothing and cannot later be flipped to
-- verified. Fixture created in-txn (its own INSERT respects the daily-cap trigger by using a tiny
-- amount); the flip is attempted and must be REFUSED by trg_guard_service_topup_status; the ledger
-- must hold ZERO rows for it either way. Rolled back.
-- expect: fixture_rejected \| t
-- expect: ledger_rows_for_rejected \| 0
-- expect: already rejected - a decided top-up cannot be re-opened
-- forbid: flip_survived \| t
BEGIN;
SELECT set_config('workhive.service_system_write', 'on', true);
CREATE TEMP TABLE _tr AS
SELECT gen_random_uuid() AS tid,
       (SELECT id FROM service_providers LIMIT 1) AS prov_id,
       (SELECT auth_uid FROM hive_members WHERE auth_uid IS NOT NULL LIMIT 1) AS payer,
       (SELECT hm.auth_uid FROM marketplace_platform_admins mpa
          JOIN hive_members hm ON hm.worker_name = mpa.worker_name AND hm.auth_uid IS NOT NULL
         LIMIT 1) AS admin_uid;
INSERT INTO service_credit_topups (id, account_type, account_id, payer_auth_uid, amount, gcash_ref, status)
SELECT tid, 'provider', prov_id, payer, 50, '999999999001', 'rejected' FROM _tr;
SELECT 'fixture_rejected | ' || (EXISTS (SELECT 1 FROM service_credit_topups
  WHERE id = (SELECT tid FROM _tr) AND status = 'rejected'));
SELECT 'ledger_rows_for_rejected | ' || count(*) FROM service_credit_ledger
 WHERE ref_id = (SELECT tid FROM _tr);
-- the flip is attempted through the USER door: an authenticated platform admin with the system
-- bypass OFF (the trusted system path is exempt by design; the claim is about reachable doors)
SELECT set_config('workhive.service_system_write', 'off', true);
GRANT SELECT ON _tr TO authenticated;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object(
  'sub', (SELECT admin_uid FROM _tr)::text, 'role', 'authenticated')::text, true);
UPDATE service_credit_topups SET status = 'verified' WHERE id = (SELECT tid FROM _tr);
ROLLBACK;
