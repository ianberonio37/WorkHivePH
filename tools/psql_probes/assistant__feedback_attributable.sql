-- feedback_attributable: a thumbs rating is attributed by the JWT — the INSERT policy binds
-- auth_uid = auth.uid(); a FORGED auth_uid is refused under the authenticated role, the caller's
-- own uid is accepted (control), and the rollback restores the count.
-- expect: policy_binds_uid \| t
-- expect: new row violates row-level security
-- expect: own_uid_accepted \| t
-- expect: restored \| t
SELECT 'policy_binds_uid | ' || EXISTS (
  SELECT 1 FROM pg_policy WHERE polrelid = 'ai_reply_feedback'::regclass
   AND COALESCE(pg_get_expr(polwithcheck, polrelid), '') ILIKE '%auth_uid = auth.uid()%');
CREATE TEMP TABLE _fa AS
SELECT hm.auth_uid AS me,
       (SELECT auth_uid FROM hive_members h2 WHERE h2.auth_uid IS NOT NULL
          AND h2.auth_uid <> hm.auth_uid LIMIT 1) AS other,
       (SELECT count(*) FROM ai_reply_feedback) AS n0
FROM hive_members hm WHERE hm.status='active' AND hm.auth_uid IS NOT NULL LIMIT 1;
GRANT SELECT ON _fa TO authenticated;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT me FROM _fa)::text, 'role', 'authenticated')::text, true);
INSERT INTO ai_reply_feedback (auth_uid, source, rating, agent, question)
SELECT (SELECT other FROM _fa), 'probe', 1, 'probe-agent', 'probe question';   -- rating is smallint (thumbs = 1/-1)
ROLLBACK;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT me FROM _fa)::text, 'role', 'authenticated')::text, true);
-- ★COUNT THE INSERT ITSELF, never a before/after total (fixed 2026-08-31). n0 is taken as postgres,
-- who sees every row; this block runs as `authenticated`, whose SELECT policy shows only their OWN
-- feedback (plus their hive's, as supervisor). Measured: postgres 1 row, this user 0. So the old
-- `count(*) = n0 + 1` compared two DIFFERENT populations and reported a perfectly good insert as a
-- refusal - the same "one measurement swept two views" mistake, inside the probe this time.
-- RETURNING counts what the statement actually wrote, in one visibility, and cannot drift.
WITH i AS (
  INSERT INTO ai_reply_feedback (auth_uid, source, rating, agent, question)
  SELECT (SELECT me FROM _fa), 'probe', 1, 'probe-agent', 'probe question'   -- rating is smallint (thumbs = 1/-1)
  RETURNING 1)
SELECT 'own_uid_accepted | ' || (count(*) = 1) FROM i;
ROLLBACK;
SELECT 'restored | ' || ((SELECT count(*) FROM ai_reply_feedback) = (SELECT n0 FROM _fa));
DROP TABLE _fa;
