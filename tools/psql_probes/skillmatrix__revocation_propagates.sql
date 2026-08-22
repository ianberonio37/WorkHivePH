-- revocation_propagates: revoking a badge reaches every surface at once — deleting one skill_badges
-- row (BEGIN/ROLLBACK) drops the base, the truth view, and the victim's worker+discipline rollup
-- badge_count together; rollback restores all three.
-- expect: all_dropped_together \| t
-- expect: restored \| t
CREATE TEMP TABLE _rv AS
SELECT sb.id AS victim, sb.worker_name, sb.discipline,
       (SELECT count(*) FROM skill_badges) AS n0,
       (SELECT count(*) FROM skill_badges s2
         WHERE s2.worker_name = sb.worker_name AND s2.discipline = sb.discipline
           AND s2.level BETWEEN 1 AND 5) AS wd0
FROM skill_badges sb WHERE sb.level BETWEEN 1 AND 5 LIMIT 1;
BEGIN;
DELETE FROM skill_badges WHERE id = (SELECT victim FROM _rv);
SELECT 'all_dropped_together | ' || (
  (SELECT count(*) FROM skill_badges) = (SELECT n0 - 1 FROM _rv)
  AND (SELECT count(*) FROM v_skill_badges_truth) = (SELECT n0 - 1 FROM _rv)
  AND COALESCE((SELECT badge_count FROM v_worker_skill_truth w
                 WHERE w.worker_name = (SELECT worker_name FROM _rv)
                   AND w.discipline = (SELECT discipline FROM _rv) LIMIT 1), 0)
      = (SELECT wd0 - 1 FROM _rv));
ROLLBACK;
SELECT 'restored | ' || ((SELECT count(*) FROM skill_badges) = (SELECT n0 FROM _rv));
DROP TABLE _rv;
