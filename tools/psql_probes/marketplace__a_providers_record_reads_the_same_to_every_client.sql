-- marketplace__a_providers_record_reads_the_same_to_every_client (GJ M9 J6, 2026-11-06, mig 20261106000009): a client
-- who never hired a provider reads that provider's "jobs done" and their latest client review exactly as the database
-- counts them - not their own RLS slice of the provider's jobs (which read 0 for every provider, to every client who had
-- not already hired them). One provider with finished work is given a client review inside a rolled-back transaction;
-- the reader is a member party to none of that provider's jobs. Restoration is asserted.
-- expect: fixture \| t
-- expect: stranger_client_jobs_done_matches \| t
-- expect: stranger_client_reads_latest_review \| t
-- expect: stranger_client_reads_no_job_row \| t
-- expect: restored \| t
BEGIN;
SELECT sp.id AS prov_id,
       (SELECT count(*) FROM service_requests sr WHERE sr.matched_provider_id = sp.id AND sr.status IN ('completed', 'settled')) AS truth_jobs,
       (SELECT sr.id FROM service_requests sr WHERE sr.matched_provider_id = sp.id AND sr.status IN ('completed', 'settled') ORDER BY sr.created_at LIMIT 1) AS job_id
  FROM service_providers sp
 WHERE EXISTS (SELECT 1 FROM service_requests sr WHERE sr.matched_provider_id = sp.id AND sr.status IN ('completed', 'settled'))
 ORDER BY sp.created_at LIMIT 1 \gset
SELECT hm.auth_uid AS reader_uid
  FROM hive_members hm
 WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM service_requests sr WHERE sr.matched_provider_id = :'prov_id'
                     AND (sr.client_auth_uid = hm.auth_uid
                          OR sr.hive_id IN (SELECT h2.hive_id FROM hive_members h2 WHERE h2.auth_uid = hm.auth_uid AND h2.status = 'active')))
   AND NOT EXISTS (SELECT 1 FROM service_providers sp WHERE sp.auth_uid = hm.auth_uid)
 ORDER BY hm.auth_uid LIMIT 1 \gset
SET LOCAL session_replication_role = replica;   -- the fixture review is written past the review birth-guard; rolled back
INSERT INTO marketplace_reviews (reviewer_name, rating, comment, request_id, direction, created_at)
VALUES ('Probe Client', 5, 'probe review - recharged and cooling', :'job_id', 'client_to_provider', now() + interval '1 minute');
SET LOCAL session_replication_role = origin;
SELECT 'fixture | ' || (:'truth_jobs'::int > 0 AND :'reader_uid' <> '');
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'reader_uid', 'role', 'authenticated')::text, true) IS NOT NULL AS claims \gset
SELECT 'stranger_client_jobs_done_matches | ' || ((SELECT completed_jobs FROM v_service_provider_truth WHERE id = :'prov_id') = :'truth_jobs'::bigint);
SELECT 'stranger_client_reads_latest_review | ' || ((SELECT latest_review_comment FROM v_service_provider_truth WHERE id = :'prov_id') = 'probe review - recharged and cooling');
-- the record is aggregates and the latest review only: the provider's jobs themselves stay the parties'
SELECT 'stranger_client_reads_no_job_row | ' || ((SELECT count(*) FROM service_requests WHERE id = :'job_id') = 0);
ROLLBACK;
SELECT 'restored | ' || NOT EXISTS (SELECT 1 FROM marketplace_reviews WHERE comment = 'probe review - recharged and cooling');
