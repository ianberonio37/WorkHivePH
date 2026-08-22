-- money-lifecycle dispute walk: a platform admin who is NOT the client adjudicates a disputed job.
-- The commission is reversed as exactly ONE provider 'adjustment' ledger row, the provider's balance
-- floors at >= 0, a second call is refused as already_adjusted (idempotent - adjusting twice would
-- refund twice), and a NON-admin caller is refused by name. Fixture: a real settled+commissioned job
-- flipped to 'disputed' INSIDE the rolled-back txn; nothing persists either direction.
-- expect: fixture_found \| t
-- expect: "adjusted": ?true
-- expect: adjustment_rows_for_job \| 1
-- expect: provider_balance_floored \| t
-- expect: "reason": ?"already_adjusted"
-- expect: Only a platform admin may adjust
-- forbid: provider_balance_floored \| f
CREATE TEMP TABLE _dj AS
SELECT sr.id AS job_id, sr.matched_provider_id AS prov_id, sr.client_auth_uid AS client_uid,
       (SELECT hm.auth_uid FROM marketplace_platform_admins mpa
          JOIN hive_members hm ON hm.worker_name = mpa.worker_name AND hm.auth_uid IS NOT NULL
         WHERE hm.auth_uid <> sr.client_auth_uid LIMIT 1) AS admin_uid,
       (SELECT hm2.auth_uid FROM hive_members hm2
         WHERE hm2.auth_uid IS NOT NULL
           AND hm2.worker_name NOT IN (SELECT worker_name FROM marketplace_platform_admins)
         LIMIT 1) AS nonadmin_uid
FROM service_requests sr
WHERE sr.status = 'settled' AND sr.client_auth_uid IS NOT NULL AND sr.matched_provider_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM service_credit_ledger l WHERE l.ref_id = sr.id AND l.entry_type = 'commission')
  AND NOT EXISTS (SELECT 1 FROM service_credit_ledger l2 WHERE l2.ref_id = sr.id AND l2.entry_type = 'adjustment')
LIMIT 1;
GRANT SELECT ON _dj TO authenticated;
SELECT 'fixture_found | ' || (EXISTS (SELECT 1 FROM _dj WHERE admin_uid IS NOT NULL AND nonadmin_uid IS NOT NULL));
BEGIN;
UPDATE service_requests SET status = 'disputed' WHERE id = (SELECT job_id FROM _dj);
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT admin_uid FROM _dj)::text, 'role', 'authenticated')::text, true);
SELECT apply_dispute_adjustment((SELECT job_id FROM _dj), 'probe: recipe replay of the 2026-08-05 walk');
-- idempotency teeth: the SECOND call inside the same txn must refuse itself
SELECT apply_dispute_adjustment((SELECT job_id FROM _dj), 'probe: second call');
RESET ROLE;
SELECT 'adjustment_rows_for_job | ' || count(*) FROM service_credit_ledger
 WHERE ref_id = (SELECT job_id FROM _dj) AND entry_type = 'adjustment' AND account_type = 'provider';
SELECT 'provider_balance_floored | ' ||
       (coalesce((SELECT sum(amount) FROM service_credit_ledger
                   WHERE account_type = 'provider' AND account_id = (SELECT prov_id FROM _dj)), 0) >= 0);
ROLLBACK;
-- refusal direction, its own txn: a NON-admin must be told by name (the RAISE aborts the txn)
BEGIN;
UPDATE service_requests SET status = 'disputed' WHERE id = (SELECT job_id FROM _dj);
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT nonadmin_uid FROM _dj)::text, 'role', 'authenticated')::text, true);
SELECT apply_dispute_adjustment((SELECT job_id FROM _dj), 'probe: non-admin refusal');
ROLLBACK;
DROP TABLE _dj;
