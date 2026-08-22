-- report_one_record_no_selfclear: reporting writes a real record (mig ...064: report_community_post
-- RPC flags under a DEFINER membership gate) and the reported AUTHOR cannot clear their own flag
-- (mig ...063's cure lives in tg_community_posts_moderation_fields: a non-supervisor's UPDATE keeps
-- a raised flag raised). SUBJECT NOTE: run as postgres, RLS does not bind — the TRIGGER is what is
-- under test here, and it reads auth.uid() from request.jwt.claims regardless of role.
-- expect: fixture_found \| t
-- expect: author_selfclear_defeated \| t
-- expect: report_rpc_flags \| t
-- expect: state_restored \| t
CREATE TEMP TABLE _rp AS
SELECT p.id AS post_id, p.hive_id, p.auth_uid AS author_uid, p.flagged AS flagged0,
       (SELECT hm2.auth_uid FROM hive_members hm2
         WHERE hm2.hive_id = p.hive_id AND hm2.status = 'active' AND hm2.auth_uid IS NOT NULL
           AND hm2.auth_uid <> p.auth_uid LIMIT 1) AS reporter_uid
FROM community_posts p
JOIN hive_members hm ON hm.hive_id = p.hive_id AND hm.auth_uid = p.auth_uid
 AND hm.status = 'active' AND hm.role <> 'supervisor'
WHERE p.auth_uid IS NOT NULL AND p.deleted_at IS NULL
  AND EXISTS (SELECT 1 FROM hive_members hm2
               WHERE hm2.hive_id = p.hive_id AND hm2.status = 'active'
                 AND hm2.auth_uid IS NOT NULL AND hm2.auth_uid <> p.auth_uid)
LIMIT 1;
SELECT 'fixture_found | ' || EXISTS (SELECT 1 FROM _rp);

BEGIN;
UPDATE community_posts SET flagged = true WHERE id = (SELECT post_id FROM _rp);
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT author_uid FROM _rp)::text, 'role', 'authenticated')::text, true);
UPDATE community_posts SET flagged = false WHERE id = (SELECT post_id FROM _rp);
SELECT 'author_selfclear_defeated | ' ||
  (SELECT flagged FROM community_posts WHERE id = (SELECT post_id FROM _rp));
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT reporter_uid FROM _rp)::text, 'role', 'authenticated')::text, true);
SELECT report_community_post((SELECT post_id FROM _rp));
SELECT 'report_rpc_flags | ' ||
  (SELECT flagged FROM community_posts WHERE id = (SELECT post_id FROM _rp));
ROLLBACK;

SELECT 'state_restored | ' || ((SELECT flagged FROM community_posts
  WHERE id = (SELECT post_id FROM _rp)) = (SELECT flagged0 FROM _rp));
DROP TABLE _rp;
