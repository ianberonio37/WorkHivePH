-- marketplace__a_disputed_job_says_who_reported_it (GJ M9 G-SVC, 2026-11-06, mig 20261106000008): when a client reports a
-- problem on a finished job, the provider - the person the review can move money against - reads on the job itself what
-- the client said and when, not only that "a problem was reported". The status-change trigger writes its own client
-- 'disputed' event in the same instant with no note; the job's read must carry the one with the reason. A finished job is
-- written and reported inside a rolled-back transaction; restoration is asserted.
-- expect: fixture \| t
-- expect: client_report_ok \| t
-- expect: provider_reads_reason \| t
-- expect: provider_reads_when \| t
-- expect: stranger_reads_no_reason \| t
-- expect: restored \| t
BEGIN;
SELECT sp.id AS prov, sp.auth_uid AS puid
  FROM service_providers sp WHERE sp.auth_uid IS NOT NULL ORDER BY sp.created_at LIMIT 1 \gset
SELECT hm.auth_uid AS cuid, hm.worker_name AS cname, hm.hive_id AS chive
  FROM hive_members hm
 WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL AND hm.auth_uid <> :'puid'
 ORDER BY hm.auth_uid LIMIT 1 \gset
SELECT hm.auth_uid AS suid
  FROM hive_members hm
 WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL AND hm.auth_uid NOT IN (:'puid', :'cuid')
   AND hm.hive_id <> :'chive'
   AND NOT EXISTS (SELECT 1 FROM hive_members h2 WHERE h2.auth_uid = hm.auth_uid AND h2.hive_id = :'chive')
   AND NOT EXISTS (SELECT 1 FROM service_providers s2 WHERE s2.auth_uid = hm.auth_uid)
 ORDER BY hm.auth_uid LIMIT 1 \gset
INSERT INTO service_requests (client_auth_uid, client_worker_name, hive_id, segment, mode, custom_scope, address, urgency,
                              status, matched_provider_id, accepted_at, completed_at)
VALUES (:'cuid', :'cname', :'chive', 'industrial', 'quote', 'probe - a disputed job says who reported it', 'Probe site', 'normal',
        'completed', :'prov', now() - interval '3 hours', now() - interval '30 minutes')
RETURNING id AS job \gset
SELECT 'fixture | ' || (:'job' <> '' AND :'suid' <> '');
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'cuid', 'role', 'authenticated')::text, true) IS NOT NULL AS c1 \gset
SELECT 'client_report_ok | ' || ((raise_service_objection(:'job', 'probe reason - the room is still warm')) ->> 'ok')::boolean;
SELECT set_config('request.jwt.claims', json_build_object('sub', :'puid', 'role', 'authenticated')::text, true) IS NOT NULL AS c2 \gset
SELECT 'provider_reads_reason | ' || ((SELECT report_reason FROM v_service_request_truth WHERE id = :'job') = 'probe reason - the room is still warm');
SELECT 'provider_reads_when | ' || ((SELECT reported_at FROM v_service_request_truth WHERE id = :'job') IS NOT NULL);
SELECT set_config('request.jwt.claims', json_build_object('sub', :'suid', 'role', 'authenticated')::text, true) IS NOT NULL AS c3 \gset
SELECT 'stranger_reads_no_reason | ' || ((SELECT count(*) FROM v_service_request_truth WHERE id = :'job') = 0);
ROLLBACK;
SELECT 'restored | ' || NOT EXISTS (SELECT 1 FROM service_requests WHERE custom_scope = 'probe - a disputed job says who reported it');
