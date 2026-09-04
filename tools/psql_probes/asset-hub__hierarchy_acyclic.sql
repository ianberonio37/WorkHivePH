-- hierarchy_acyclic: a node cannot become its own ancestor through any edit path. A cycle in the asset
-- tree is not a cosmetic defect - every consumer that walks parent_id (the tree render, roll-ups,
-- ancestor-scoped queries) either hangs or silently truncates, and the damage is invisible until someone
-- opens the branch. This is pure DB truth, so it belongs in a replayable recipe rather than a browser walk
-- that can only re-observe what SQL can assert.
-- NOTE ON THE TEETH SHAPE: nothing in the schema REFUSES a cycle (a parent_id cycle is not expressible as
-- a CHECK), so unlike the uniqueness probes the guard here is the DETECTOR, not the database. The teeth
-- therefore prove the detector BITES: a cycle minted inside BEGIN/ROLLBACK must be seen. A detector that
-- cannot be made to fire was never testing anything.
-- Self-grounding: the cycle is built from a live parent/child pair, never from invented ids.
-- expect: nodes_checked \| [1-9][0-9]*
-- expect: cyclic_paths \| 0
-- expect: teeth_pair_found \| t
-- expect: teeth_cycle_detected \| t
-- expect: rows_restored_after_rollback \| t

-- the invariant as it stands, with its population printed beside it (non-vacuity)
WITH RECURSIVE walk AS (
  SELECT id, parent_id, 1 AS depth, ARRAY[id] AS path, false AS cyc FROM asset_nodes
  UNION ALL
  SELECT w.id, n.parent_id, w.depth + 1, w.path || n.id, n.id = ANY(w.path)
  FROM walk w JOIN asset_nodes n ON n.id = w.parent_id
  WHERE NOT w.cyc AND w.depth < 60)
SELECT 'nodes_checked | ' || (SELECT count(*) FROM asset_nodes)::text
     || E'\ncyclic_paths | ' || count(*) FILTER (WHERE cyc)::text FROM walk;

-- a live parent/child pair to bend into a cycle
CREATE TEMP TABLE _fix AS
SELECT c.id AS child_id, c.parent_id AS parent_id, (SELECT count(*) FROM asset_nodes) AS n0
FROM asset_nodes c WHERE c.parent_id IS NOT NULL LIMIT 1;
SELECT 'teeth_pair_found | ' || EXISTS (SELECT 1 FROM _fix);

BEGIN;
-- TEETH: point the PARENT at its own child, so parent -> child -> parent is a cycle
UPDATE asset_nodes SET parent_id = (SELECT child_id FROM _fix)
 WHERE id = (SELECT parent_id FROM _fix);
WITH RECURSIVE walk AS (
  SELECT id, parent_id, 1 AS depth, ARRAY[id] AS path, false AS cyc FROM asset_nodes
  UNION ALL
  SELECT w.id, n.parent_id, w.depth + 1, w.path || n.id, n.id = ANY(w.path)
  FROM walk w JOIN asset_nodes n ON n.id = w.parent_id
  WHERE NOT w.cyc AND w.depth < 60)
SELECT 'teeth_cycle_detected | ' || (count(*) FILTER (WHERE cyc) > 0) FROM walk;
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM asset_nodes) = (SELECT n0 FROM _fix));
