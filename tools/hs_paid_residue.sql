-- hs_paid_residue.sql - what the HS walks' rows PAID, taken back once the rows are gone (run by every prove_hive_scale_*
-- harness after its cleanup; idempotent - a clean hive answers 0 everywhere).
-- WHY (2026-10-30): the harnesses delete their rows with triggers off (session_replication_role = replica) so a cleanup
-- writes no audit trail of its own - and so the DELETE triggers that take back XP never ran. A day of bursts, shifts and
-- races left 246 reply awards and 10 "first post" awards standing for rows that no longer existed (Rowena read 630
-- community XP for one real post; every member read ~80 high), and worker_achievements held 13,260 logbook, 5,900 post
-- and 2,160 PM XP for entries that were gone. The leaderboard and achievements lists the walks then READ were the walks'
-- own residue. A walk's cleanup owes what its rows' triggers wrote - paid totals included.
-- Each block deletes the ledger rows of a gone source and takes back only what was still standing (reversed_at null):
-- a reversed award was already taken back by its trigger.
BEGIN;
CREATE TEMP TABLE _hs ON COMMIT DROP AS
  SELECT DISTINCT worker_name FROM public.hive_members WHERE hive_id = '30303030-3030-4030-8030-303030303030';

WITH gone AS (
  DELETE FROM public.community_reply_xp_awards a
   WHERE a.hive_id = '30303030-3030-4030-8030-303030303030'
     AND NOT EXISTS (SELECT 1 FROM public.community_replies r WHERE r.id = a.reply_id)
  RETURNING a.author_name, a.hive_id, a.xp_awarded, a.reversed_at),
owed AS (SELECT author_name, hive_id, sum(xp_awarded) AS amt FROM gone WHERE reversed_at IS NULL GROUP BY 1, 2)
UPDATE public.community_xp x SET xp_total = GREATEST(0, x.xp_total - o.amt), updated_at = now()
  FROM owed o WHERE x.worker_name = o.author_name AND x.hive_id = o.hive_id;

WITH gone AS (
  DELETE FROM public.community_post_xp_awards a
   WHERE a.hive_id = '30303030-3030-4030-8030-303030303030'
     AND NOT EXISTS (SELECT 1 FROM public.community_posts p WHERE p.id = a.post_id)
  RETURNING a.author_name, a.hive_id, a.xp_awarded, a.reversed_at),
owed AS (SELECT author_name, hive_id, sum(xp_awarded) AS amt FROM gone WHERE reversed_at IS NULL GROUP BY 1, 2)
UPDATE public.community_xp x SET xp_total = GREATEST(0, x.xp_total - o.amt), updated_at = now()
  FROM owed o WHERE x.worker_name = o.author_name AND x.hive_id = o.hive_id;

WITH gone AS (
  DELETE FROM public.community_reaction_xp_awards a
   WHERE a.hive_id = '30303030-3030-4030-8030-303030303030'
     AND NOT EXISTS (SELECT 1 FROM public.community_posts p WHERE p.id = a.post_id)
  RETURNING a.author_name, a.hive_id, a.xp_awarded),
owed AS (SELECT author_name, hive_id, sum(xp_awarded) AS amt FROM gone WHERE xp_awarded > 0 GROUP BY 1, 2)
UPDATE public.community_xp x SET xp_total = GREATEST(0, x.xp_total - o.amt), updated_at = now()
  FROM owed o WHERE x.worker_name = o.author_name AND x.hive_id = o.hive_id;

-- achievement XP names its source by action; the logbook pays under five of them (trg_logbook_xp_reverse takes back
-- every one of them by source_id), a post under one, a PM completion and a calculation under one each
WITH gone AS (
  DELETE FROM public.achievement_xp_log l
   WHERE l.worker_name IN (SELECT worker_name FROM _hs)
     AND l.source_id IS NOT NULL AND l.source_id <> ''
     AND ((l.source_action IN ('logbook_submit', 'logbook_close', 'detailed_entry', 'safety_entry', 'breakdown_root_cause')
            AND NOT EXISTS (SELECT 1 FROM public.logbook b WHERE b.id::text = l.source_id))
       OR (l.source_action = 'community_post'
            AND NOT EXISTS (SELECT 1 FROM public.community_posts p WHERE p.id::text = l.source_id))
       OR (l.source_action = 'pm_complete'
            AND NOT EXISTS (SELECT 1 FROM public.pm_completions c WHERE c.id::text = l.source_id))
       OR (l.source_action = 'calc_run'
            AND NOT EXISTS (SELECT 1 FROM public.engineering_calcs e WHERE e.id::text = l.source_id)))
  RETURNING l.worker_name, l.achievement_id, l.xp_earned, l.reversed_at),
owed AS (SELECT worker_name, achievement_id, sum(xp_earned) AS amt FROM gone
          WHERE reversed_at IS NULL AND xp_earned > 0 GROUP BY 1, 2)
UPDATE public.worker_achievements w SET xp_total = GREATEST(0, w.xp_total - o.amt)
  FROM owed o WHERE w.worker_name = o.worker_name AND w.achievement_id = o.achievement_id;

SELECT 'paid_residue_left | ' || (
    (SELECT count(*) FROM public.community_reply_xp_awards a WHERE a.hive_id = '30303030-3030-4030-8030-303030303030'
       AND NOT EXISTS (SELECT 1 FROM public.community_replies r WHERE r.id = a.reply_id))
  + (SELECT count(*) FROM public.community_post_xp_awards a WHERE a.hive_id = '30303030-3030-4030-8030-303030303030'
       AND NOT EXISTS (SELECT 1 FROM public.community_posts p WHERE p.id = a.post_id)))::text;
COMMIT;
