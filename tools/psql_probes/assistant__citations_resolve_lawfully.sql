-- citations_resolve_lawfully: the assistant's grounding reads are the SAME truth surfaces the
-- pages use, under the caller's own JWT — each of the six grounding relations exists, and the
-- tenant-scoped ones enforce their scope under an authenticated member (spot check: a foreign
-- hive's logbook rows are invisible to the member the assistant answers).
-- expect: grounding_relations \| 6
-- expect: member_logbook_scoped \| t
SELECT 'grounding_relations | ' || count(*) FROM information_schema.tables
WHERE table_name IN ('v_logbook_truth','schedule_items','v_skill_badges_truth',
                     'v_inventory_items_truth','v_pm_compliance_truth','voice_journal_entries');
CREATE TEMP TABLE _cl AS
SELECT hm.hive_id, hm.auth_uid FROM hive_members hm
WHERE hm.status='active' AND hm.auth_uid IS NOT NULL LIMIT 1;
GRANT SELECT ON _cl TO authenticated;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT auth_uid FROM _cl)::text, 'role', 'authenticated')::text, true);
SELECT 'member_logbook_scoped | ' ||
  ((SELECT count(*) FROM v_logbook_truth WHERE hive_id <> (SELECT hive_id FROM _cl)) = 0);
ROLLBACK;
DROP TABLE _cl;
