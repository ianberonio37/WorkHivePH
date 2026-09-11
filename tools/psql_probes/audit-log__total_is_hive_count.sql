-- total_is_hive_count (P-C tile == DB canonical / cap-is-not-a-total, 2026-09-05): audit-log loads
-- the latest 500 entries and once labelled that cap as the hive's total. The page now takes a
-- count-only read for the true total. This recipe holds the two facts the honest label rests on:
-- the cap actually BITES on the main hives (so the '(N total)' branch is exercised, not decorative),
-- and every entry names its hive and actor (a total that counts orphan rows is not the hive's).
-- expect: cap_bites_on_main_hives \| t
-- expect: entries_name_hive_and_actor \| t
SELECT 'cap_bites_on_main_hives | ' || ((SELECT count(*) FROM (SELECT hive_id FROM hive_audit_log GROUP BY hive_id HAVING count(*) > 500) x) >= 1);
SELECT 'entries_name_hive_and_actor | ' || ((SELECT count(*) FROM hive_audit_log WHERE hive_id IS NULL OR actor IS NULL OR actor = '') = 0);
