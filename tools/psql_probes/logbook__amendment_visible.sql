-- amendment_visible: amending a CLOSED entry leaves a visible audit trail — hive_audit_log carries
-- amend_closed_logbook_entry actions with a named actor and target, distinct from ordinary edits.
-- expect: amendments_logged \| [1-9][0-9]*
-- expect: anonymous_amendments \| 0
SELECT 'amendments_logged | ' || count(*) FROM hive_audit_log
WHERE action = 'amend_closed_logbook_entry';
SELECT 'anonymous_amendments | ' || count(*) FROM hive_audit_log
WHERE action = 'amend_closed_logbook_entry'
  AND (actor IS NULL OR btrim(actor) = '' OR target_type IS DISTINCT FROM 'logbook');
