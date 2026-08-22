-- mtbf_own_failures: MTBF is computed from each machine's OWN failure history — the fn partitions
-- by machine (LAG ... PARTITION BY machine), counts only Breakdown / Corrective entries, and bounds
-- the window with its period parameter. Read from the function's own source, plus a live sanity
-- call: no machine's MTBF is negative.
-- expect: partitions_by_machine \| t
-- expect: breakdown_only \| t
-- expect: window_bounded \| t
-- expect: negative_mtbf_rows \| 0
SELECT 'partitions_by_machine | ' || (prosrc ILIKE '%PARTITION BY machine%') FROM pg_proc WHERE proname='get_mtbf_by_machine';
SELECT 'breakdown_only | ' || (prosrc ILIKE '%Breakdown / Corrective%') FROM pg_proc WHERE proname='get_mtbf_by_machine';
SELECT 'window_bounded | ' || (prosrc ILIKE '%p_period_days%interval%') FROM pg_proc WHERE proname='get_mtbf_by_machine';
SELECT 'negative_mtbf_rows | ' || count(*) FROM (
  SELECT * FROM get_mtbf_by_machine((SELECT hive_id FROM hive_members WHERE status='active' LIMIT 1))
) g WHERE (to_jsonb(g)->>'mtbf_days')::numeric < 0;
