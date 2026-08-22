-- alert_count_agrees: index and alert-hub read the SAME alert truth — v_alert_truth is the one
-- source (index reads the signature/critical banner from it, alert-hub reads its feed from it), and
-- the view's alert_kind vocabulary is closed so neither page can see a kind the other cannot.
-- expect: view_rows \| [1-9][0-9]*
-- expect: kind_vocabulary_closed \| t
SELECT 'view_rows | ' || count(*) FROM v_alert_truth;
SELECT 'kind_vocabulary_closed | ' || (count(*) = 0) FROM v_alert_truth
WHERE alert_kind NOT IN ('signature','anomaly','amc','risk','inventory','pm');
