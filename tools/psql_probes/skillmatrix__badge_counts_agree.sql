-- badge_counts_agree: the badge number is ONE number everywhere — v_skill_badges_truth mirrors the
-- base table, and EVERY v_worker_skill_truth row's badge_count equals the recomputed count for that
-- worker+discipline (levels 1..5). A whole-view SUM would be the wrong oracle: the rollup is
-- per-MEMBERSHIP by construction, so a worker active in two hives rightly appears under both
-- (168 rollup vs 148 base here is semantics, not drift). Population printed (non-vacuity).
-- expect: base_badges \| [1-9][0-9]*
-- expect: truth_view_agrees \| t
-- expect: rollup_rows \| [1-9][0-9]*
-- expect: rollup_disagreements \| 0
SELECT 'base_badges | ' || count(*) FROM skill_badges;
SELECT 'truth_view_agrees | ' ||
  ((SELECT count(*) FROM skill_badges) = (SELECT count(*) FROM v_skill_badges_truth));
SELECT 'rollup_rows | ' || count(*) FROM v_worker_skill_truth;
SELECT 'rollup_disagreements | ' || count(*) FROM v_worker_skill_truth w
WHERE w.badge_count <> (SELECT count(*) FROM skill_badges sb
                         WHERE sb.worker_name = w.worker_name AND sb.discipline = w.discipline
                           AND sb.level BETWEEN 1 AND 5);
