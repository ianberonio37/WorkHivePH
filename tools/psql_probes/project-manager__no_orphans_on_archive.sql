-- no_orphans_on_archive: deleting a project leaves no orphan item, link, role, progress log or change
-- order. An orphan here is silent by nature - the project disappears from every list while its change
-- orders and progress logs sit in their tables forever, counted by any aggregate that does not join back
-- to a project.
-- TWO CLAIMS, deliberately separate, because they fail independently: (1) every FK that REFERENCES
-- projects declares an explicit delete rule, so a NEW child table cannot quietly arrive with NO ACTION
-- and start orphaning; and (2) the rules actually FIRE - a live project with children is deleted inside
-- BEGIN/ROLLBACK and every child must be gone in the same transaction. Rule-declared and rule-works are
-- different facts; a schema can pass the first and fail the second after a table is rebuilt.
-- The child count is taken from the CATALOG, not from a list written here, so a sixth child table added
-- tomorrow is covered without editing this probe.
-- Self-grounding: the victim is a project that actually has children.
-- expect: fks_referencing_projects \| [1-9][0-9]*
-- expect: fks_without_explicit_delete_rule \| 0
-- expect: teeth_victim_found \| t
-- expect: teeth_children_before \| [1-9][0-9]*
-- expect: teeth_children_after \| 0
-- expect: rows_restored_after_rollback \| t

SELECT 'fks_referencing_projects | ' || count(*)::text
     || E'\nfks_without_explicit_delete_rule | ' || count(*) FILTER (WHERE rc.delete_rule NOT IN ('CASCADE','SET NULL'))::text
FROM information_schema.table_constraints tc
JOIN information_schema.referential_constraints rc ON rc.constraint_name = tc.constraint_name
JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' AND ccu.table_name = 'projects';

CREATE TEMP TABLE _fix AS
SELECT p.id AS victim,
       (SELECT count(*) FROM project_items i WHERE i.project_id = p.id)
     + (SELECT count(*) FROM project_links l WHERE l.project_id = p.id)
     + (SELECT count(*) FROM project_roles r WHERE r.project_id = p.id)
     + (SELECT count(*) FROM project_progress_logs g WHERE g.project_id = p.id)
     + (SELECT count(*) FROM project_change_orders c WHERE c.project_id = p.id) AS kids,
       (SELECT count(*) FROM projects) AS n0
FROM projects p
WHERE (SELECT count(*) FROM project_items i WHERE i.project_id = p.id)
    + (SELECT count(*) FROM project_links l WHERE l.project_id = p.id)
    + (SELECT count(*) FROM project_roles r WHERE r.project_id = p.id)
    + (SELECT count(*) FROM project_progress_logs g WHERE g.project_id = p.id)
    + (SELECT count(*) FROM project_change_orders c WHERE c.project_id = p.id) > 0
LIMIT 1;
SELECT 'teeth_victim_found | ' || EXISTS (SELECT 1 FROM _fix);
SELECT 'teeth_children_before | ' || coalesce((SELECT kids FROM _fix), 0)::text;

BEGIN;
DELETE FROM projects WHERE id = (SELECT victim FROM _fix);
SELECT 'teeth_children_after | ' || (
    (SELECT count(*) FROM project_items i WHERE i.project_id = (SELECT victim FROM _fix))
  + (SELECT count(*) FROM project_links l WHERE l.project_id = (SELECT victim FROM _fix))
  + (SELECT count(*) FROM project_roles r WHERE r.project_id = (SELECT victim FROM _fix))
  + (SELECT count(*) FROM project_progress_logs g WHERE g.project_id = (SELECT victim FROM _fix))
  + (SELECT count(*) FROM project_change_orders c WHERE c.project_id = (SELECT victim FROM _fix)))::text;
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM projects) = (SELECT n0 FROM _fix));
