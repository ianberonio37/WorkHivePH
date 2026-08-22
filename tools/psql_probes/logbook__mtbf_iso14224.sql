-- mtbf_iso14224: MTBF counts only FAILURE events (ISO 14224's line between corrective and the
-- rest) — the fn filters Breakdown / Corrective, partitions per machine, and the capture supports
-- it: breakdown entries carry downtime while preventive/inspection entries do not.
-- expect: fn_breakdown_only \| t
-- expect: fn_partitions_per_machine \| t
-- expect: breakdowns_with_downtime \| [1-9][0-9]*
-- expect: preventive_with_downtime \| 0
SELECT 'fn_breakdown_only | ' || (prosrc ILIKE '%Breakdown / Corrective%') FROM pg_proc WHERE proname='get_mtbf_by_machine';
SELECT 'fn_partitions_per_machine | ' || (prosrc ILIKE '%PARTITION BY machine%') FROM pg_proc WHERE proname='get_mtbf_by_machine';
SELECT 'breakdowns_with_downtime | ' || count(*) FROM logbook
WHERE maintenance_type = 'Breakdown / Corrective' AND downtime_hours > 0;
SELECT 'preventive_with_downtime | ' || count(*) FROM logbook
WHERE maintenance_type = 'Preventive Maintenance' AND downtime_hours > 0;
