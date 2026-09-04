-- links_tenant_bound: every linked object, across all the domains a project can link into, resolves in
-- the PROJECT'S OWN hive. `project_links` is polymorphic (link_type, link_id), so no foreign key can carry
-- this - a polymorphic reference cannot be constrained - and tenancy through the link table is therefore
-- exactly the place it is easiest to lose: one wrong link_id and a project page renders another hive's
-- asset, logbook entry or completion, with no error anywhere.
-- The check resolves each link_type against ITS OWN table and compares hive_id to the project's, rather
-- than trusting `project_links.hive_id` - the link row's own column agreeing with the project proves only
-- that the ROW is filed correctly, not that the thing it POINTS AT belongs here. Those are different
-- claims and only the second one is the oracle.
-- Teeth: no constraint can prevent this, so the guard is the DETECTOR - a cross-hive link minted inside
-- BEGIN/ROLLBACK must be seen. A tenancy check that cannot be made to fire is decoration.
-- Self-grounding: the bad link is built from a live project and a live foreign-hive asset.
-- expect: links_checked \| [1-9][0-9]*
-- expect: link_domains \| [1-9][0-9]*
-- expect: cross_hive_links \| 0
-- expect: teeth_fixture_found \| t
-- expect: teeth_cross_hive_detected \| [1-9][0-9]*
-- expect: rows_restored_after_rollback \| t

SELECT 'links_checked | ' || count(*)::text
     || E'\nlink_domains | ' || count(DISTINCT link_type)::text
FROM project_links;

-- resolve each domain against its own table; a link is bad if nothing with that id lives in the project's hive
SELECT 'cross_hive_links | ' || count(*)::text
FROM project_links pl JOIN projects p ON p.id = pl.project_id
WHERE (pl.link_type = 'asset'            AND NOT EXISTS (SELECT 1 FROM asset_nodes a      WHERE a.id::text = pl.link_id::text AND a.hive_id = p.hive_id))
   OR (pl.link_type = 'inventory_item'   AND NOT EXISTS (SELECT 1 FROM inventory_items i  WHERE i.id::text = pl.link_id::text AND i.hive_id = p.hive_id))
   OR (pl.link_type = 'logbook'          AND NOT EXISTS (SELECT 1 FROM logbook l          WHERE l.id::text = pl.link_id::text AND l.hive_id = p.hive_id))
   OR (pl.link_type = 'pm_completion'    AND NOT EXISTS (SELECT 1 FROM pm_completions c   WHERE c.id::text = pl.link_id::text AND c.hive_id = p.hive_id))
   OR (pl.link_type = 'engineering_calc' AND NOT EXISTS (SELECT 1 FROM engineering_calcs e WHERE e.id::text = pl.link_id::text AND e.hive_id = p.hive_id));

-- a live asset link, and a live asset belonging to a DIFFERENT hive to bend it onto
CREATE TEMP TABLE _fix AS
SELECT pl.id AS link_id_row, p.hive_id AS project_hive,
       (SELECT a.id FROM asset_nodes a WHERE a.hive_id IS DISTINCT FROM p.hive_id LIMIT 1) AS foreign_asset,
       (SELECT count(*) FROM project_links) AS n0
FROM project_links pl JOIN projects p ON p.id = pl.project_id
WHERE pl.link_type = 'asset' LIMIT 1;
SELECT 'teeth_fixture_found | ' || EXISTS (SELECT 1 FROM _fix WHERE foreign_asset IS NOT NULL);

BEGIN;
UPDATE project_links SET link_id = (SELECT foreign_asset::text FROM _fix)
 WHERE id = (SELECT link_id_row FROM _fix);
SELECT 'teeth_cross_hive_detected | ' || count(*)::text
FROM project_links pl JOIN projects p ON p.id = pl.project_id
WHERE pl.link_type = 'asset'
  AND NOT EXISTS (SELECT 1 FROM asset_nodes a WHERE a.id::text = pl.link_id::text AND a.hive_id = p.hive_id);
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM project_links) = (SELECT n0 FROM _fix));
