-- Deleting an asset node keeps ONE PM summary for its asset, instead of refusing the delete (2026-10-27).
--
-- pm_knowledge holds one summary per asset: per node through pm_knowledge_one_per_asset (hive_id, asset_id), and per asset
-- NAME for a PM asset with no node through pm_knowledge_one_per_unlinked_asset (20261012000070). Its link to the node is
-- ON DELETE SET NULL. So when a node is deleted and an unlinked summary for the same (hive, asset name) already exists,
-- SET NULL turns the node's summary into a SECOND unlinked one, the unique index refuses it, and the whole delete fails
-- with a raw 23505 - the supervisor's delete, the 30-day purge of a recoverable delete, and a hive's cascade alike.
-- Found by the psql probe asset-hub__delete_orphans_nothing on a clean reseed; the local reset had been working around
-- the same collision by ordering (reset.py, 2026-10-26) without the product ever being fixed.
--
-- The rule: before a node is deleted, its summary is dropped WHEN an unlinked summary for the same asset already exists
-- (that one is the asset's summary from now on - two would be the duplicate 20261012000070 collapsed). Otherwise the
-- summary is kept and unlinked as before. Nothing else about the delete changes.

BEGIN;

CREATE OR REPLACE FUNCTION public.pm_knowledge_unlink_without_duplicate()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  DELETE FROM public.pm_knowledge k
   WHERE k.asset_id = OLD.id
     AND EXISTS (SELECT 1 FROM public.pm_knowledge u
                  WHERE u.asset_id IS NULL
                    AND COALESCE(u.hive_id, '00000000-0000-0000-0000-000000000000'::uuid)
                        = COALESCE(k.hive_id, '00000000-0000-0000-0000-000000000000'::uuid)
                    AND u.asset_name = k.asset_name);
  RETURN OLD;
END
$$;
-- a trigger function, never called through the API
REVOKE ALL ON FUNCTION public.pm_knowledge_unlink_without_duplicate() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_asset_node_delete_keeps_one_pm_summary ON public.asset_nodes;
CREATE TRIGGER trg_asset_node_delete_keeps_one_pm_summary
  BEFORE DELETE ON public.asset_nodes
  FOR EACH ROW EXECUTE FUNCTION public.pm_knowledge_unlink_without_duplicate();

COMMIT;
