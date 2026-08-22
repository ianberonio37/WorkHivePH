-- level_recomputed: level and XP agree everywhere, verified against the page's OWN threshold
-- function xpForLevel(n) = floor(100 * n^1.8) — the stored current_level must equal the highest n
-- whose threshold the row's xp_total meets (checked live: 352286 XP -> 93, threshold(93)=349241<=xp,
-- threshold(94)=355988>xp). Zero disagreements required, and the population is printed so an empty
-- table cannot masquerade as agreement (non-vacuity).
-- expect: rows_checked \| [1-9][0-9]*
-- expect: disagreements \| 0
WITH implied AS (
  SELECT worker_name, achievement_id, xp_total, current_level,
         COALESCE((SELECT max(n) FROM generate_series(0, 300) n
                    WHERE floor(100 * power(n, 1.8)) <= xp_total), 0) AS level_implied
  FROM worker_achievements)
SELECT 'rows_checked | ' || count(*) FROM implied;
WITH implied AS (
  SELECT xp_total, current_level,
         COALESCE((SELECT max(n) FROM generate_series(0, 300) n
                    WHERE floor(100 * power(n, 1.8)) <= xp_total), 0) AS level_implied
  FROM worker_achievements)
SELECT 'disagreements | ' || count(*) FROM implied WHERE current_level <> level_implied;
