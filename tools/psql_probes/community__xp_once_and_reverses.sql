-- xp_once_and_reverses: community XP obeys the rules the TRIGGER actually implements, and each award can
-- only ever be claimed once. `trg_community_post_xp` awards 50 for an author's FIRST live post, and it does
-- not defend that with application logic - it writes `community_post_xp_awards (post_id, reason)` with
-- ON CONFLICT DO NOTHING and only increments XP when that insert actually claimed a row
-- (`GET DIAGNOSTICS claimed = ROW_COUNT`). So the once-only guarantee IS the unique key on that table: if
-- the key goes, a replayed trigger silently pays twice and no other code notices.
-- WHY A RECIPE: this is a unique index plus one insert - pure DB truth a browser walk can only re-observe.
-- Teeth BOTH directions inside BEGIN/ROLLBACK: re-claiming an award already held must be REFUSED (23505),
-- and a FREE (post_id, reason) pair must be ACCEPTED - that is what separates a working once-only rule from
-- a table that rejects everything.
-- Self-grounding: both fixtures are derived from live rows, never invented ids.
-- expect: once_only_index_present \| t
-- expect: awards_checked \| [1-9][0-9]*
-- expect: duplicate_award_pairs \| 0
-- expect: duplicate key value violates unique constraint
-- expect: control_accepted \| t
-- expect: rows_restored_after_rollback \| t

SELECT 'once_only_index_present | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE tablename = 'community_post_xp_awards'
   AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%post_id%' AND indexdef ILIKE '%reason%');

SELECT 'awards_checked | ' || count(*)::text FROM community_post_xp_awards;
SELECT 'duplicate_award_pairs | ' || count(*)::text FROM (
  SELECT post_id, reason FROM community_post_xp_awards GROUP BY 1,2 HAVING count(*) > 1) d;

-- a held award to replay, and a live post with NO award to act as the control
CREATE TEMP TABLE _fix AS
SELECT a.post_id AS held_post, a.reason AS held_reason, a.author_name, a.hive_id, a.xp_awarded,
       (SELECT p.id FROM community_posts p
         WHERE NOT EXISTS (SELECT 1 FROM community_post_xp_awards w WHERE w.post_id = p.id) LIMIT 1) AS free_post,
       (SELECT count(*) FROM community_post_xp_awards) AS n0
FROM community_post_xp_awards a LIMIT 1;

BEGIN;
-- TEETH: claiming the SAME (post, reason) twice must be refused by the key, not by application code
INSERT INTO community_post_xp_awards (post_id, reason, author_name, hive_id, xp_awarded)
SELECT held_post, held_reason, author_name, hive_id, xp_awarded FROM _fix;
ROLLBACK;

BEGIN;
-- CONTROL: a post that holds no award must accept one, or the key rejects everything
INSERT INTO community_post_xp_awards (post_id, reason, author_name, hive_id, xp_awarded)
SELECT free_post, held_reason, author_name, hive_id, xp_awarded FROM _fix WHERE free_post IS NOT NULL;
SELECT 'control_accepted | ' || EXISTS (
  SELECT 1 FROM community_post_xp_awards w JOIN _fix f ON w.post_id = f.free_post);
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM community_post_xp_awards) = (SELECT n0 FROM _fix));
