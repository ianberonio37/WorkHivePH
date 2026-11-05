-- community__a_moderated_post_tells_its_author_and_its_reporters (GJ M9 G-MOD, 2026-11-06, mig 20261106000003): a
-- supervisor's decision on a reported post is recorded only by moderate_reported_post, and it tells the author and the
-- reporter (by push, and in what each reads back). Three people of one hive, all inside a rolled-back transaction.
-- expect: fixture \| t
-- expect: report_carries_reporter_account \| t
-- expect: supervisor_cannot_forge_the_record \| t
-- expect: author_cannot_moderate \| refused
-- expect: supervisor_keeps \| kept
-- expect: author_pushed \| t
-- expect: reporter_pushed \| t
-- expect: author_not_told_who_reported \| t
-- expect: author_reads_back \| kept
-- expect: reporter_reads_back \| kept
-- expect: restored \| t
CREATE TEMP TABLE _gm AS
SELECT (SELECT m.auth_uid FROM hive_members m WHERE m.hive_id = h.id AND m.role = 'supervisor' AND m.status = 'active' ORDER BY m.worker_name LIMIT 1) AS sup,
       (SELECT m.auth_uid FROM hive_members m WHERE m.hive_id = h.id AND m.role = 'worker' AND m.status = 'active' ORDER BY m.worker_name LIMIT 1) AS author,
       (SELECT m.auth_uid FROM hive_members m WHERE m.hive_id = h.id AND m.role = 'worker' AND m.status = 'active' ORDER BY m.worker_name OFFSET 1 LIMIT 1) AS reporter,
       h.id AS hive, now() AS t0, (SELECT count(*) FROM community_posts) AS n0
  FROM hives h WHERE h.name = 'Batangas Refinery Maintenance';
GRANT SELECT ON _gm TO authenticated;
CREATE FUNCTION pg_temp.as_user(uid uuid) RETURNS void LANGUAGE sql AS $f$
  SELECT set_config('request.jwt.claims', json_build_object('sub', uid::text, 'role', 'authenticated')::text, true);
$f$;
CREATE FUNCTION pg_temp.try(sql text) RETURNS text LANGUAGE plpgsql AS $f$
DECLARE v text;
BEGIN EXECUTE sql INTO v; RETURN coalesce(v, 'NULL');
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused';
  WHEN others THEN RETURN 'error ' || SQLSTATE || ' ' || SQLERRM;
END $f$;
BEGIN;
INSERT INTO community_posts (hive_id, author_name, auth_uid, content, category)
SELECT g.hive, (SELECT display_name FROM worker_profiles WHERE auth_uid = g.author), g.author, 'PROBE-GMOD selling my spare bearings, message me', 'general' FROM _gm g;
SELECT 'fixture | ' || ((SELECT sup FROM _gm) IS NOT NULL AND (SELECT reporter FROM _gm) IS NOT NULL AND EXISTS (SELECT 1 FROM community_posts WHERE content LIKE 'PROBE-GMOD%'));
-- the reporter reports it, as the page does: the rpc, then the audit line
SET LOCAL ROLE authenticated;
SELECT pg_temp.as_user((SELECT reporter FROM _gm));
SELECT public.report_community_post((SELECT id FROM community_posts WHERE content LIKE 'PROBE-GMOD%'));
INSERT INTO hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
SELECT g.hive, 'x', 'report_post', 'community_posts', p.id::text, 'probe', jsonb_build_object('reason', 'spam') FROM _gm g, community_posts p WHERE p.content LIKE 'PROBE-GMOD%';
RESET ROLE;
SELECT 'report_carries_reporter_account | ' || EXISTS (SELECT 1 FROM hive_audit_log a, _gm g WHERE a.action = 'report_post' AND a.created_at >= g.t0 AND a.meta->>'actor_auth_uid' = g.reporter::text);
-- a supervisor writing the record directly is pinned
SET LOCAL ROLE authenticated;
SELECT pg_temp.as_user((SELECT sup FROM _gm));
UPDATE community_posts SET moderated_by = 'forged', moderation_outcome = 'kept' WHERE content LIKE 'PROBE-GMOD%';
RESET ROLE;
SELECT 'supervisor_cannot_forge_the_record | ' || ((SELECT moderated_by FROM community_posts WHERE content LIKE 'PROBE-GMOD%') IS NULL);
-- the author cannot decide on their own reported post
SET LOCAL ROLE authenticated;
SELECT pg_temp.as_user((SELECT author FROM _gm));
SELECT 'author_cannot_moderate | ' || CASE WHEN pg_temp.try($q$SELECT public.moderate_reported_post((SELECT id FROM community_posts WHERE content LIKE 'PROBE-GMOD%'), true, 'mine')::text$q$) LIKE 'refused%' THEN 'refused' ELSE 'ALLOWED' END;
-- the supervisor keeps it, with a reason
SELECT pg_temp.as_user((SELECT sup FROM _gm));
SELECT 'supervisor_keeps | ' || ((public.moderate_reported_post((SELECT id FROM community_posts WHERE content LIKE 'PROBE-GMOD%'), true, 'trade talk is allowed here'))->>'outcome');
RESET ROLE;
SELECT 'author_pushed | ' || EXISTS (SELECT 1 FROM service_outbox o, _gm g WHERE o.created_at >= g.t0 AND o.payload->'auth_uids' ? g.author::text AND o.payload->>'title' = 'Your post was reviewed and kept');
SELECT 'reporter_pushed | ' || EXISTS (SELECT 1 FROM service_outbox o, _gm g WHERE o.created_at >= g.t0 AND o.payload->'auth_uids' ? g.reporter::text AND o.payload->>'title' = 'Your report was reviewed');
SELECT 'author_not_told_who_reported | ' || NOT EXISTS (SELECT 1 FROM service_outbox o, _gm g, worker_profiles w WHERE o.created_at >= g.t0 AND o.payload->'auth_uids' ? g.author::text AND w.auth_uid = g.reporter AND o.payload->>'body' LIKE '%' || w.display_name || '%');
SET LOCAL ROLE authenticated;
SELECT pg_temp.as_user((SELECT author FROM _gm));
SELECT 'author_reads_back | ' || coalesce((SELECT outcome FROM public.my_moderation_news() WHERE kind = 'your_post' AND words LIKE 'PROBE-GMOD%' LIMIT 1), 'NOTHING');
SELECT pg_temp.as_user((SELECT reporter FROM _gm));
SELECT 'reporter_reads_back | ' || coalesce((SELECT outcome FROM public.my_moderation_news() WHERE kind = 'your_report' AND words LIKE 'PROBE-GMOD%' LIMIT 1), 'NOTHING');
ROLLBACK;
SELECT 'restored | ' || ((SELECT count(*) FROM community_posts) = (SELECT n0 FROM _gm) AND NOT EXISTS (SELECT 1 FROM community_posts WHERE content LIKE 'PROBE-GMOD%'));
