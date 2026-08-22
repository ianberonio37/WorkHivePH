-- send_audited: every send attempt leaves an automation_log row on BOTH paths. The FN half of this
-- claim (send-report-email audits before returning, success AND failure) is carried by the row's
-- source reading; what psql can prove is the TRAIL MECHANISM: the audit table exists with the shape
-- the fn writes, and it ACCEPTS both the success-shape and the failure-shape row (BEGIN/ROLLBACK -
-- nothing persists). Data-count expectations are deliberately absent: this local stack has sent no
-- real email, and a trail with zero rows is a truthful zero, not a broken trail.
-- expect: audit_columns \| 6
-- expect: success_shape_accepted \| t
-- expect: failure_shape_accepted \| t
-- expect: rows_restored_after_rollback \| t
-- forbid: ERROR:
SELECT 'audit_columns | ' || count(*) FROM information_schema.columns
WHERE table_name = 'automation_log'
  AND column_name IN ('id', 'job_name', 'hive_id', 'triggered_at', 'status', 'detail');
SELECT 'pre_count' AS k, count(*) AS n FROM automation_log WHERE job_name = 'send_report_email' \gset pre_
BEGIN;
INSERT INTO automation_log (job_name, hive_id, triggered_at, status, detail)
SELECT 'send_report_email', h.id, now(), 'success', 'Sent 1 report(s) to probe@example.com'
FROM hives h LIMIT 1;
SELECT 'success_shape_accepted | t';
INSERT INTO automation_log (job_name, hive_id, triggered_at, status, detail)
SELECT 'send_report_email', h.id, now(), 'failed', 'probe: provider message carried into the trail'
FROM hives h LIMIT 1;
SELECT 'failure_shape_accepted | t';
ROLLBACK;
SELECT 'rows_restored_after_rollback | ' ||
       (count(*) = :pre_n) FROM automation_log WHERE job_name = 'send_report_email';
