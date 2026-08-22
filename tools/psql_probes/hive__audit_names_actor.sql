-- audit_names_actor: every hive audit row NAMES its actor and action — an audit trail with blank
-- actors is a log, not accountability. Population printed (non-vacuity).
-- expect: audit_rows \| [1-9][0-9]*
-- expect: blank_actor \| 0
-- expect: blank_action \| 0
SELECT 'audit_rows | ' || count(*) FROM hive_audit_log;
SELECT 'blank_actor | ' || count(*) FROM hive_audit_log WHERE actor IS NULL OR btrim(actor) = '';
SELECT 'blank_action | ' || count(*) FROM hive_audit_log WHERE action IS NULL OR btrim(action) = '';
