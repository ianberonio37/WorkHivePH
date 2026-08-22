-- deferred_not_completed: a skipped PM is never counted as done — the status vocabulary separates
-- done from skipped, both exist in live data (non-vacuity), and the compliance numerator counts
-- ONLY status='done' (read from the fn's own source).
-- expect: done_rows \| [1-9][0-9]*
-- expect: skipped_rows \| [1-9][0-9]*
-- expect: rogue_statuses \| 0
-- expect: numerator_done_only \| t
SELECT 'done_rows | '    || count(*) FROM pm_completions WHERE status = 'done';
SELECT 'skipped_rows | ' || count(*) FROM pm_completions WHERE status = 'skipped';
SELECT 'rogue_statuses | ' || count(*) FROM pm_completions WHERE status NOT IN ('done','skipped');
-- the fn aligns columns (pc.status        = 'done') so the pattern tolerates whitespace
SELECT 'numerator_done_only | ' || (prosrc ~* $rx$pc\.status\s*=\s*'done'$rx$)
FROM pg_proc WHERE proname = 'get_pm_compliance_smrp';
