-- na_excluded_explicitly: the compliance denominator is SCHEDULE-derived over ACTIVE scope only —
-- inactive items are excluded by an explicit predicate, and the denominator is computed from
-- frequency over the period (never from however many records happen to exist), floor-guarded so a
-- long-frequency item still counts once.
-- expect: active_only \| t
-- expect: schedule_derived \| t
-- expect: floor_guarded \| t
SELECT 'active_only | '      || (prosrc ~* $x$status\s*=\s*'active'$x$)      FROM pg_proc WHERE proname='get_pm_compliance_smrp';
SELECT 'schedule_derived | ' || (prosrc ~* $x$p_period_days\s*/\s*.*frequency_days$x$) FROM pg_proc WHERE proname='get_pm_compliance_smrp';
SELECT 'floor_guarded | '    || (prosrc ILIKE '%GREATEST(1,%')               FROM pg_proc WHERE proname='get_pm_compliance_smrp';
