-- Asset Nodes Bridge Backfill — re-runnable.
--
-- The original asset_brain_backfill (20260508000010) populated legacy_asset_id
-- and pm_asset_id at cut-over time. Any asset_node inserted AFTER that one-shot
-- (via the asset wizard, the seeder's reliability fixtures, the CMMS sync flow,
-- or a supervisor-approved node) does NOT inherit those bridges automatically.
--
-- Symptom: asset-brain-query/index.ts fetchAssetTimeline silently returns an
-- empty logbook/PM array when both bridges are NULL, even though the asset has
-- real history under its tag in legacy assets or pm_assets. The Asset Brain
-- narrative then loses grounding for those assets.
--
-- This migration ships two things:
--   (1) A re-runnable backfill pass that fills any NULL bridge by case-insensitive
--       (hive_id, tag/name) match against the legacy tables.
--   (2) A BEFORE INSERT trigger on asset_nodes that auto-populates bridges going
--       forward, so the same gap never silently re-opens for new assets.
--
-- Why a trigger rather than rewiring every writer (wizard / seeder / CMMS sync):
-- there are 5+ insert paths and growing. A single trigger guarantees the
-- invariant ("if a matching legacy/pm row exists, the bridge is populated")
-- regardless of who writes.
--
-- Skills consulted: architect (invariant as trigger, not as code in every writer),
-- data-engineer (case-insensitive match + COALESCE so we never overwrite an
-- explicitly-set bridge), multitenant-engineer (hive_id is part of every match),
-- maintenance-expert (tag vs name fallback mirrors how engineers actually label
-- equipment in the field).

BEGIN;

-- ── 1. Re-runnable backfill: fill any NULL bridge by matching against the
--      legacy tables on (hive_id, lower(tag/name)).

UPDATE public.asset_nodes AS n
SET pm_asset_id = pa.id
FROM public.pm_assets AS pa
WHERE n.pm_asset_id IS NULL
  AND n.hive_id = pa.hive_id
  AND (
       lower(n.tag)  = lower(NULLIF(pa.tag_id, ''))
    OR lower(n.tag)  = lower(pa.asset_name)
    OR lower(n.name) = lower(pa.asset_name)
  );

UPDATE public.asset_nodes AS n
SET legacy_asset_id = a.id
FROM public.assets AS a
WHERE n.legacy_asset_id IS NULL
  AND n.hive_id = a.hive_id
  AND (
       lower(n.tag)  = lower(NULLIF(a.asset_id, ''))
    OR lower(n.tag)  = lower(NULLIF(a.name, ''))
    OR lower(n.name) = lower(NULLIF(a.name, ''))
    OR lower(n.name) = lower(NULLIF(a.asset_id, ''))
  );

-- ── 2. Trigger: keep the invariant for every new or updated asset_node.

CREATE OR REPLACE FUNCTION public.populate_asset_node_bridges()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_pm_id   uuid;
  v_leg_id  text;
BEGIN
  -- Only resolve bridges when hive_id is set; solo-mode nodes (hive_id NULL)
  -- are not in the legacy hive-scoped tables anyway.
  IF NEW.hive_id IS NULL THEN
    RETURN NEW;
  END IF;

  IF NEW.pm_asset_id IS NULL THEN
    SELECT pa.id INTO v_pm_id
    FROM public.pm_assets pa
    WHERE pa.hive_id = NEW.hive_id
      AND (
           lower(NEW.tag)  = lower(NULLIF(pa.tag_id, ''))
        OR lower(NEW.tag)  = lower(pa.asset_name)
        OR lower(NEW.name) = lower(pa.asset_name)
      )
    LIMIT 1;
    NEW.pm_asset_id := COALESCE(NEW.pm_asset_id, v_pm_id);
  END IF;

  IF NEW.legacy_asset_id IS NULL THEN
    SELECT a.id INTO v_leg_id
    FROM public.assets a
    WHERE a.hive_id = NEW.hive_id
      AND (
           lower(NEW.tag)  = lower(NULLIF(a.asset_id, ''))
        OR lower(NEW.tag)  = lower(NULLIF(a.name, ''))
        OR lower(NEW.name) = lower(NULLIF(a.name, ''))
        OR lower(NEW.name) = lower(NULLIF(a.asset_id, ''))
      )
    LIMIT 1;
    NEW.legacy_asset_id := COALESCE(NEW.legacy_asset_id, v_leg_id);
  END IF;

  RETURN NEW;
END
$$;

COMMENT ON FUNCTION public.populate_asset_node_bridges() IS
  'BEFORE INSERT/UPDATE trigger on asset_nodes that fills legacy_asset_id and pm_asset_id by case-insensitive match against legacy assets and pm_assets. Ensures Asset Brain timeline never silently empties for an asset that has real history under a sibling table.';

DROP TRIGGER IF EXISTS trg_populate_asset_node_bridges ON public.asset_nodes;

CREATE TRIGGER trg_populate_asset_node_bridges
BEFORE INSERT OR UPDATE OF tag, name, hive_id, pm_asset_id, legacy_asset_id
ON public.asset_nodes
FOR EACH ROW
EXECUTE FUNCTION public.populate_asset_node_bridges();

-- ── 3. Provenance row so we can see the backfill outcome in automation_log.

DO $$
DECLARE
  cnt_total       bigint;
  cnt_pm_null     bigint;
  cnt_leg_null    bigint;
  cnt_both_null   bigint;
BEGIN
  SELECT count(*) INTO cnt_total      FROM public.asset_nodes WHERE hive_id IS NOT NULL;
  SELECT count(*) INTO cnt_pm_null    FROM public.asset_nodes WHERE hive_id IS NOT NULL AND pm_asset_id     IS NULL;
  SELECT count(*) INTO cnt_leg_null   FROM public.asset_nodes WHERE hive_id IS NOT NULL AND legacy_asset_id IS NULL;
  SELECT count(*) INTO cnt_both_null  FROM public.asset_nodes WHERE hive_id IS NOT NULL AND pm_asset_id IS NULL AND legacy_asset_id IS NULL;

  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'automation_log') THEN
    INSERT INTO public.automation_log (job_name, status, detail)
    VALUES (
      'asset_nodes_bridge_backfill',
      CASE WHEN cnt_both_null = 0 THEN 'success' ELSE 'partial' END,
      format(
        'hive_nodes=%s pm_bridge_null=%s legacy_bridge_null=%s both_null=%s',
        cnt_total, cnt_pm_null, cnt_leg_null, cnt_both_null
      )
    );
  END IF;
END
$$;

COMMIT;
