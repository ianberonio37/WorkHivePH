-- anomaly_idempotent: running the anomaly engine twice does not double its signals — the second
-- compute_anomaly_signals run lands on the same rows (upsert semantics), count unchanged. The fn
-- gates on hive membership, so it is called under an active member's claims. Teeth inside
-- BEGIN/ROLLBACK; baseline restored afterwards.
-- expect: run1_wrote_or_kept \| t
-- expect: run2_no_doubling \| t
-- expect: restored \| t
CREATE TEMP TABLE _ai AS
SELECT (SELECT count(*) FROM anomaly_signals) AS n0,
       hm.hive_id, hm.auth_uid
FROM hive_members hm WHERE hm.status='active' AND hm.auth_uid IS NOT NULL LIMIT 1;
BEGIN;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT auth_uid FROM _ai)::text, 'role', 'authenticated')::text, true);
SELECT count(*) FROM compute_anomaly_signals((SELECT hive_id FROM _ai));
CREATE TEMP TABLE _c1 AS SELECT count(*) AS n FROM anomaly_signals;
SELECT count(*) FROM compute_anomaly_signals((SELECT hive_id FROM _ai));
SELECT 'run1_wrote_or_kept | ' || ((SELECT n FROM _c1) >= (SELECT n0 FROM _ai));
SELECT 'run2_no_doubling | ' || ((SELECT count(*) FROM anomaly_signals) = (SELECT n FROM _c1));
ROLLBACK;
SELECT 'restored | ' || ((SELECT count(*) FROM anomaly_signals) = (SELECT n0 FROM _ai));
DROP TABLE _ai;
