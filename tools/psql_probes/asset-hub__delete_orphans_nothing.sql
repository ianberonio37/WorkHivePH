-- delete_orphans_nothing: deleting an asset node orphans nothing - FMEA modes, strategies, sensor links
-- and edges go with it, by DECLARED FK rules rather than by whichever delete path happened to run. An
-- orphan here is invisible: the node is gone from the tree while its FMEA modes and sensor readings sit
-- in the tables forever, counted by every aggregate that does not join back to a node.
-- WHY A RECIPE: this is FK topology plus one delete - pure DB truth. A browser walk can only re-observe it.
-- TWO ASSERTIONS, deliberately separate: (1) every FK that REFERENCES asset_nodes declares an explicit
-- delete rule, so a NEW child table cannot quietly arrive with NO ACTION and start orphaning; and (2) the
-- rules actually FIRE - a live node with children is deleted inside BEGIN/ROLLBACK and the children must
-- be gone in the same transaction. Rule-present and rule-works are different claims and both are checked.
-- Self-grounding: the victim is a live node that HAS children, never an invented id.
-- expect: fks_referencing_asset_nodes \| [1-9][0-9]*
-- expect: fks_without_explicit_delete_rule \| 0
-- expect: teeth_victim_found \| t
-- expect: teeth_children_before \| [1-9][0-9]*
-- expect: teeth_children_after \| 0
-- expect: rows_restored_after_rollback \| t

SELECT 'fks_referencing_asset_nodes | ' || count(*)::text
     || E'\nfks_without_explicit_delete_rule | ' || count(*) FILTER (WHERE rc.delete_rule NOT IN ('CASCADE','SET NULL'))::text
FROM information_schema.table_constraints tc
JOIN information_schema.referential_constraints rc ON rc.constraint_name = tc.constraint_name
JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' AND ccu.table_name = 'asset_nodes';

-- a live node that actually has cascading children, so the teeth measure something
CREATE TEMP TABLE _fix AS
SELECT n.id AS victim,
       (SELECT count(*) FROM rcm_fmea_modes m WHERE m.asset_id = n.id) AS kids,
       (SELECT count(*) FROM asset_nodes) AS n0
FROM asset_nodes n
WHERE EXISTS (SELECT 1 FROM rcm_fmea_modes m WHERE m.asset_id = n.id)
LIMIT 1;
SELECT 'teeth_victim_found | ' || EXISTS (SELECT 1 FROM _fix);
SELECT 'teeth_children_before | ' || coalesce((SELECT kids FROM _fix), 0)::text;

BEGIN;
DELETE FROM asset_nodes WHERE id = (SELECT victim FROM _fix);
SELECT 'teeth_children_after | ' ||
       (SELECT count(*) FROM rcm_fmea_modes m WHERE m.asset_id = (SELECT victim FROM _fix))::text;
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM asset_nodes) = (SELECT n0 FROM _fix));
