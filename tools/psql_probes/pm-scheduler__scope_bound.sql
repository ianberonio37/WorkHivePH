-- scope_bound: a scope item cannot be ticked for an asset outside the PM's own scope. A completion
-- carries its own asset_id AND a scope_item_id; if those two disagree, the tick was recorded against a
-- machine the scope item does not belong to - and every compliance figure that groups by asset then
-- counts it under the wrong one, silently and forever.
-- HOW IT IS (AND IS NOT) ENFORCED: `pm_completions.scope_item_id` has a real FK to pm_scope_items, so the
-- scope item must EXIST - but a cross-table agreement between two asset_ids is not expressible as a CHECK,
-- so nothing in the schema forces them to MATCH. The guard is therefore the DETECTOR, and the teeth mint a
-- real mismatch inside BEGIN/ROLLBACK and require it to be seen. A detector that cannot be made to fire
-- was never testing anything.
-- Both agreements are checked, not just the asset: hive_id must match too, because a completion filed
-- under the wrong HIVE is the tenancy version of the same defect.
-- Self-grounding: the mismatch is built from two live rows, never invented ids.
-- expect: completions_with_scope \| [1-9][0-9]*
-- expect: asset_mismatch \| 0
-- expect: hive_mismatch \| 0
-- expect: teeth_fixture_found \| t
-- expect: teeth_mismatch_detected \| [1-9][0-9]*
-- expect: rows_restored_after_rollback \| t

SELECT 'completions_with_scope | ' || count(*)::text
     || E'\nasset_mismatch | ' || count(*) FILTER (WHERE c.asset_id IS DISTINCT FROM si.asset_id)::text
     || E'\nhive_mismatch | '  || count(*) FILTER (WHERE c.hive_id  IS DISTINCT FROM si.hive_id)::text
FROM pm_completions c JOIN pm_scope_items si ON si.id = c.scope_item_id;

-- a live completion, plus a DIFFERENT asset to bend it onto
CREATE TEMP TABLE _fix AS
SELECT c.id AS completion_id, c.asset_id AS own_asset,
       (SELECT a.asset_id FROM pm_scope_items a WHERE a.asset_id IS DISTINCT FROM c.asset_id LIMIT 1) AS foreign_asset,
       (SELECT count(*) FROM pm_completions) AS n0
FROM pm_completions c WHERE c.scope_item_id IS NOT NULL LIMIT 1;
SELECT 'teeth_fixture_found | ' || EXISTS (SELECT 1 FROM _fix WHERE foreign_asset IS NOT NULL);

BEGIN;
UPDATE pm_completions SET asset_id = (SELECT foreign_asset FROM _fix)
 WHERE id = (SELECT completion_id FROM _fix);
SELECT 'teeth_mismatch_detected | ' || count(*)::text
FROM pm_completions c JOIN pm_scope_items si ON si.id = c.scope_item_id
WHERE c.asset_id IS DISTINCT FROM si.asset_id;
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM pm_completions) = (SELECT n0 FROM _fix));
