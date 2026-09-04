-- delete_respects_links: deleting a calc that a project links to must not silently break the project.
-- HOW IT IS ACTUALLY ENFORCED, and why that took looking twice: projects link to calcs through
-- `project_links (link_type, link_id)`, a POLYMORPHIC link, so it carries no foreign key and no delete
-- rule - and the first read of that said "unenforced, holds by luck". It is not: `trg_cleanup_project_links`
-- on engineering_calcs removes the matching links when a calc is deleted. A foreign key CANNOT express a
-- polymorphic reference, so a trigger is the right mechanism here, not a missing one. The absence of an FK
-- is therefore asserted DELIBERATELY (so the day someone adds one, this line changes and gets noticed)
-- alongside the trigger that does the real work.
-- Teeth: deleting a linked calc inside BEGIN/ROLLBACK must leave ZERO links pointing at it. A cleanup that
-- cannot be observed firing is indistinguishable from no cleanup at all.
-- Self-grounding: the victim is a calc a project actually links to, never an invented id.
-- expect: calc_links_present \| [1-9][0-9]*
-- expect: dangling_calc_links \| 0
-- expect: enforced_by_foreign_key \| f
-- expect: cleanup_trigger_present \| t
-- expect: teeth_victim_found \| t
-- expect: teeth_links_after_delete \| 0
-- expect: rows_restored_after_rollback \| t

SELECT 'calc_links_present | ' || count(*)::text
FROM project_links WHERE link_type = 'engineering_calc';

SELECT 'dangling_calc_links | ' || count(*)::text
FROM project_links pl
WHERE pl.link_type = 'engineering_calc'
  AND NOT EXISTS (SELECT 1 FROM engineering_calcs c WHERE c.id::text = pl.link_id::text);

SELECT 'enforced_by_foreign_key | ' || EXISTS (
  SELECT 1 FROM information_schema.table_constraints tc
  JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
  WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = 'project_links'
    AND ccu.table_name = 'engineering_calcs');

SELECT 'cleanup_trigger_present | ' || EXISTS (
  SELECT 1 FROM pg_trigger
  WHERE tgrelid = 'public.engineering_calcs'::regclass AND NOT tgisinternal
    AND tgname = 'trg_cleanup_project_links');

CREATE TEMP TABLE _fix AS
SELECT c.id AS victim, (SELECT count(*) FROM engineering_calcs) AS n0
FROM engineering_calcs c
WHERE EXISTS (SELECT 1 FROM project_links pl
               WHERE pl.link_type = 'engineering_calc' AND pl.link_id::text = c.id::text)
LIMIT 1;
SELECT 'teeth_victim_found | ' || EXISTS (SELECT 1 FROM _fix);

BEGIN;
DELETE FROM engineering_calcs WHERE id = (SELECT victim FROM _fix);
SELECT 'teeth_links_after_delete | ' || count(*)::text
FROM project_links pl
WHERE pl.link_type = 'engineering_calc' AND pl.link_id::text = (SELECT victim::text FROM _fix);
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM engineering_calcs) = (SELECT n0 FROM _fix));
