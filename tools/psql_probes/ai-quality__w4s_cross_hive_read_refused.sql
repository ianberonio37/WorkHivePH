-- cross_hive_read_refused (ai-quality, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every
-- hive-scoped table this page reads (ai_cost_log, ai_reply_feedback) must refuse a foreign hive in the DATABASE. RLS USING
-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with
-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in
-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.
-- expect: ai_cost_log_fixture \| t
-- expect: ai_cost_log_foreign_rows \| 0
-- expect: ai_cost_log_own_rows_gt0 \| t
-- expect: ai_reply_feedback_fixture \| t
-- expect: ai_reply_feedback_foreign_rows \| 0
-- expect: ai_reply_feedback_own_rows_gt0 \| t

CREATE TEMP TABLE _fx_ai_cost_log AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM ai_cost_log x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM ai_cost_log x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_ai_cost_log TO authenticated;
SELECT 'ai_cost_log_fixture | ' || ((SELECT me FROM _fx_ai_cost_log) IS NOT NULL AND (SELECT foreign_hive FROM _fx_ai_cost_log) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_ai_cost_log)::text, 'role','authenticated')::text, true);
SELECT 'ai_cost_log_foreign_rows | ' || (SELECT count(*) FROM ai_cost_log WHERE hive_id = (SELECT foreign_hive FROM _fx_ai_cost_log));
SELECT 'ai_cost_log_own_rows_gt0 | ' || ((SELECT count(*) FROM ai_cost_log WHERE hive_id = (SELECT mine FROM _fx_ai_cost_log)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_ai_reply_feedback AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM ai_reply_feedback x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM ai_reply_feedback x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_ai_reply_feedback TO authenticated;
SELECT 'ai_reply_feedback_fixture | ' || ((SELECT me FROM _fx_ai_reply_feedback) IS NOT NULL AND (SELECT foreign_hive FROM _fx_ai_reply_feedback) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_ai_reply_feedback)::text, 'role','authenticated')::text, true);
SELECT 'ai_reply_feedback_foreign_rows | ' || (SELECT count(*) FROM ai_reply_feedback WHERE hive_id = (SELECT foreign_hive FROM _fx_ai_reply_feedback));
SELECT 'ai_reply_feedback_own_rows_gt0 | ' || ((SELECT count(*) FROM ai_reply_feedback WHERE hive_id = (SELECT mine FROM _fx_ai_reply_feedback)) > 0);
ROLLBACK;
