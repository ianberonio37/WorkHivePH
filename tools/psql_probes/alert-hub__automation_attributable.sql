-- automation_attributable: every automation run is attributable — automation_log rows all carry
-- job_name, triggered_at and status, and each job is CONSISTENTLY scoped: 100% hive-scoped or 100%
-- platform-scoped, never mixed (a mixed job is one whose failures cannot be routed to an owner).
-- expect: log_rows \| [1-9][0-9]*
-- expect: unattributed \| 0
-- expect: mixed_scope_jobs \| 0
SELECT 'log_rows | ' || count(*) FROM automation_log;
SELECT 'unattributed | ' || count(*) FROM automation_log
WHERE job_name IS NULL OR triggered_at IS NULL OR status IS NULL;
SELECT 'mixed_scope_jobs | ' || count(*) FROM (
  SELECT job_name FROM automation_log GROUP BY job_name
  HAVING count(*) FILTER (WHERE hive_id IS NULL) > 0
     AND count(*) FILTER (WHERE hive_id IS NOT NULL) > 0) m;
