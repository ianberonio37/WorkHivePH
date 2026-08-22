-- reputation_live: the person card's reputation is LIVE — get_community_reputation reads
-- community_xp.xp_total for (worker, hive), the same row profile + leaderboard read directly.
-- Teeth in BOTH directions: without claims the RPC's membership gate returns NOTHING (the A01
-- refusal is part of the contract), and under an active member's claims the RPC's xp equals the
-- table row byte-for-byte. Population printed (non-vacuity).
-- expect: xp_rows \| [1-9][0-9]*
-- expect: fn_reads_community_xp \| t
-- expect: ungated_call_refused \| t
-- expect: rpc_equals_table \| t
SELECT 'xp_rows | ' || count(*) FROM community_xp;
SELECT 'fn_reads_community_xp | ' ||
  (prosrc ILIKE '%community_xp%') FROM pg_proc WHERE proname = 'get_community_reputation';

CREATE TEMP TABLE _rep AS
SELECT cx.worker_name, cx.hive_id, cx.xp_total,
       (SELECT hm.auth_uid FROM hive_members hm
         WHERE hm.hive_id = cx.hive_id AND hm.status = 'active' AND hm.auth_uid IS NOT NULL
         LIMIT 1) AS member_uid
FROM community_xp cx
WHERE cx.xp_total > 0
  AND EXISTS (SELECT 1 FROM hive_members hm
               WHERE hm.hive_id = cx.hive_id AND hm.status = 'active' AND hm.auth_uid IS NOT NULL)
ORDER BY cx.xp_total DESC LIMIT 1;

SELECT 'ungated_call_refused | ' || NOT EXISTS (
  SELECT 1 FROM get_community_reputation(
    (SELECT worker_name FROM _rep), (SELECT hive_id FROM _rep)));

BEGIN;
SELECT set_config('request.jwt.claims',
                  json_build_object('sub', (SELECT member_uid FROM _rep)::text, 'role', 'authenticated')::text,
                  true);
SELECT 'rpc_equals_table | ' || (
  (SELECT g.xp_total FROM get_community_reputation(
      (SELECT worker_name FROM _rep), (SELECT hive_id FROM _rep)) g)
  = (SELECT xp_total FROM _rep));
ROLLBACK;
DROP TABLE _rep;
