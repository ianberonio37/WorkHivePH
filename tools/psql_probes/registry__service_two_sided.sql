-- two_sided_same_object (service job): ONE object, THREE identities, each asking the server as
-- itself under SET LOCAL ROLE authenticated + its own claims. The job's real buyer reads it, the
-- matched provider reads the SAME row, and an unrelated member with a valid uid reads ZERO of it
-- (a refusal, not an anon artifact). Fixture derived live; every read inside one probe run.
-- expect: fixture_found \| t
-- expect: buyer_reads_own_job \| 1
-- expect: provider_reads_same_job \| 1
-- expect: stranger_reads_none \| 0
CREATE TEMP TABLE _tw AS
SELECT sr.id AS job_id, sr.client_auth_uid AS buyer_uid,
       (SELECT hm.auth_uid FROM hive_members hm
         WHERE hm.worker_name = sp.worker_name AND hm.auth_uid IS NOT NULL LIMIT 1) AS provider_uid,
       (SELECT hm2.auth_uid FROM hive_members hm2
         WHERE hm2.status = 'active' AND hm2.auth_uid IS NOT NULL
           AND hm2.auth_uid <> sr.client_auth_uid
           AND hm2.worker_name <> sp.worker_name
           AND hm2.auth_uid NOT IN (
             SELECT h3.auth_uid FROM hive_members h3
              WHERE h3.worker_name = sp.worker_name AND h3.auth_uid IS NOT NULL)
         LIMIT 1) AS stranger_uid
FROM service_requests sr
JOIN service_providers sp ON sp.id = sr.matched_provider_id
WHERE sr.client_auth_uid IS NOT NULL
LIMIT 1;
GRANT SELECT ON _tw TO authenticated;
SELECT 'fixture_found | ' || (EXISTS (SELECT 1 FROM _tw WHERE provider_uid IS NOT NULL AND stranger_uid IS NOT NULL));
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT buyer_uid FROM _tw)::text, 'role', 'authenticated')::text, true);
SELECT 'buyer_reads_own_job | ' || count(*) FROM service_requests WHERE id = (SELECT job_id FROM _tw);
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT provider_uid FROM _tw)::text, 'role', 'authenticated')::text, true);
SELECT 'provider_reads_same_job | ' || count(*) FROM service_requests WHERE id = (SELECT job_id FROM _tw);
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT stranger_uid FROM _tw)::text, 'role', 'authenticated')::text, true);
SELECT 'stranger_reads_none | ' || count(*) FROM service_requests WHERE id = (SELECT job_id FROM _tw);
ROLLBACK;
DROP TABLE _tw;
