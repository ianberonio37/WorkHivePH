-- mttr_repair_time: MTTR averages REPAIR time over repair events only — the fn averages
-- downtime_hours over Breakdown / Corrective entries with downtime > 0, and a live call returns
-- no negative or absurd mean.
-- expect: fn_repairs_only \| t
-- expect: fn_averages_downtime \| t
-- expect: absurd_mttr_rows \| 0
SELECT 'fn_repairs_only | ' || (prosrc ILIKE '%Breakdown / Corrective%' AND prosrc ~* $x$downtime_hours\s+>\s+0$x$)  -- the fn aligns columns, tolerate whitespace
FROM pg_proc WHERE proname='get_mttr_by_machine';
SELECT 'fn_averages_downtime | ' || (prosrc ILIKE '%AVG(downtime_hours)%') FROM pg_proc WHERE proname='get_mttr_by_machine';
SELECT 'absurd_mttr_rows | ' || count(*) FROM (
  SELECT * FROM get_mttr_by_machine((SELECT hive_id FROM hive_members WHERE status='active' LIMIT 1))
) g WHERE (to_jsonb(g)->>'mttr_hours')::numeric < 0 OR (to_jsonb(g)->>'mttr_hours')::numeric > 10000;
