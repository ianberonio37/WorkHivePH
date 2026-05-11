-- Phase 5a: Parallel UUID FKs for the legacy text-keyed asset bridges.
--
-- Today logbook and inventory_items reference assets via text keys:
--   logbook.asset_ref_id            text -> assets.id text
--   inventory_items.linked_asset_ids text[] -> assets.id text values
--
-- The canonical asset identity is asset_nodes.id (uuid), with
-- asset_nodes.legacy_asset_id (text) carrying the bridge value to old
-- assets.id rows. The audit's recommendation (CANONICAL_SOURCES_AUDIT.md
-- D1) is to migrate every writer to the uuid path; this Phase 5a does the
-- safe half of that:
--
--   1. Add a uuid FK column alongside each text bridge.
--   2. Backfill the new column from the existing text bridge via the
--      asset_nodes.legacy_asset_id lookup. Idempotent: only fills NULLs.
--   3. Trigger-maintain the uuid column going forward so writers don't
--      need to know about it. Inserts that carry the text bridge get the
--      uuid auto-resolved BEFORE the row hits the table.
--   4. Indexes for the new FK so downstream readers see the same query
--      perf the text path has today.
--
-- This migration does NOT drop the text bridges. Phase 5b (deferred) will
-- migrate readers + drop the legacy columns once every consumer reads the
-- uuid path. Until then both paths stay valid and the trigger keeps the
-- uuid path populated for every new write.
--
-- Skills consulted: architect (parallel-cutover pattern, FK invariant by
-- trigger), data-engineer (single-statement backfill keyed on the
-- existing index, EXISTS check before UPDATE), multitenant-engineer
-- (hive_id scope on every match so cross-tenant bridging is impossible),
-- maintenance-expert (asset identity continuity across the migration).

BEGIN;

-- ── 1. logbook.asset_node_id ─────────────────────────────────────────────────
-- ON DELETE SET NULL mirrors the existing asset_ref_id FK semantics.

ALTER TABLE public.logbook
  ADD COLUMN IF NOT EXISTS asset_node_id uuid
    REFERENCES public.asset_nodes(id) ON DELETE SET NULL;

-- Backfill: resolve every existing logbook row's asset_ref_id to the matching
-- asset_node via (hive_id, legacy_asset_id). Solo-mode rows (hive_id NULL)
-- can't be bridged because asset_nodes is hive-scoped; they stay NULL,
-- which is correct (no canonical node exists for them).

UPDATE public.logbook AS l
SET asset_node_id = n.id
FROM public.asset_nodes AS n
WHERE l.asset_node_id IS NULL
  AND l.asset_ref_id IS NOT NULL
  AND l.hive_id IS NOT NULL
  AND n.hive_id = l.hive_id
  AND n.legacy_asset_id = l.asset_ref_id;

-- Trigger: resolve on every INSERT/UPDATE that touches asset_ref_id or
-- hive_id, so writers never need to manage asset_node_id themselves.
-- SECURITY DEFINER + locked search_path so cron/edge function sessions
-- can't subvert resolution.

CREATE OR REPLACE FUNCTION public.resolve_logbook_asset_node_id()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_catalog
AS $$
BEGIN
  -- Only resolve when the uuid path is unset AND the text bridge is set
  -- AND we have a hive to scope by. Explicit user-provided asset_node_id
  -- always wins (no overwrite).
  IF NEW.asset_node_id IS NULL
     AND NEW.asset_ref_id IS NOT NULL
     AND NEW.hive_id IS NOT NULL THEN
    SELECT n.id INTO NEW.asset_node_id
    FROM public.asset_nodes n
    WHERE n.hive_id = NEW.hive_id
      AND n.legacy_asset_id = NEW.asset_ref_id
    LIMIT 1;
  END IF;
  RETURN NEW;
END
$$;

COMMENT ON FUNCTION public.resolve_logbook_asset_node_id() IS
  'Phase 5a auto-bridge: resolves logbook.asset_node_id (uuid) from asset_ref_id (text) via asset_nodes.legacy_asset_id on every INSERT/UPDATE. Writers do not need to know about the uuid column.';

DROP TRIGGER IF EXISTS trg_resolve_logbook_asset_node_id ON public.logbook;

CREATE TRIGGER trg_resolve_logbook_asset_node_id
BEFORE INSERT OR UPDATE OF asset_ref_id, hive_id, asset_node_id
ON public.logbook
FOR EACH ROW
EXECUTE FUNCTION public.resolve_logbook_asset_node_id();

-- Index so the new FK has the same lookup perf the text bridge has today.
CREATE INDEX IF NOT EXISTS idx_logbook_asset_node_id
  ON public.logbook (asset_node_id) WHERE asset_node_id IS NOT NULL;

-- ── 2. inventory_items.linked_asset_node_ids ────────────────────────────────
-- text[] -> uuid[]. No FK because Postgres doesn't enforce FK on array
-- elements; the trigger + asset_nodes.id uuid type provides the integrity
-- contract.

ALTER TABLE public.inventory_items
  ADD COLUMN IF NOT EXISTS linked_asset_node_ids uuid[] DEFAULT '{}'::uuid[];

-- Backfill: for each inventory_items row with non-empty linked_asset_ids,
-- map every text id to the corresponding asset_nodes.id via the same
-- (hive_id, legacy_asset_id) bridge. Rows without a hive scope can't bridge.

UPDATE public.inventory_items AS i
SET linked_asset_node_ids = (
  SELECT COALESCE(array_agg(DISTINCT n.id) FILTER (WHERE n.id IS NOT NULL), '{}'::uuid[])
  FROM unnest(i.linked_asset_ids) AS legacy_id
  LEFT JOIN public.asset_nodes n
         ON n.hive_id        = i.hive_id
        AND n.legacy_asset_id = legacy_id
)
WHERE i.hive_id IS NOT NULL
  AND i.linked_asset_ids IS NOT NULL
  AND array_length(i.linked_asset_ids, 1) > 0
  AND (i.linked_asset_node_ids IS NULL OR array_length(i.linked_asset_node_ids, 1) IS NULL);

-- Trigger: resolve on every INSERT/UPDATE that touches linked_asset_ids
-- or hive_id. Same SECURITY DEFINER + locked search_path pattern.

CREATE OR REPLACE FUNCTION public.resolve_inventory_linked_asset_node_ids()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_catalog
AS $$
BEGIN
  -- Only resolve when the uuid array is empty/null AND the text array
  -- has content AND we have a hive scope. Explicit user-provided uuid
  -- array always wins (no overwrite).
  IF (NEW.linked_asset_node_ids IS NULL
       OR array_length(NEW.linked_asset_node_ids, 1) IS NULL)
     AND NEW.linked_asset_ids IS NOT NULL
     AND array_length(NEW.linked_asset_ids, 1) > 0
     AND NEW.hive_id IS NOT NULL THEN
    NEW.linked_asset_node_ids := (
      SELECT COALESCE(array_agg(DISTINCT n.id) FILTER (WHERE n.id IS NOT NULL), '{}'::uuid[])
      FROM unnest(NEW.linked_asset_ids) AS legacy_id
      LEFT JOIN public.asset_nodes n
             ON n.hive_id        = NEW.hive_id
            AND n.legacy_asset_id = legacy_id
    );
  END IF;
  RETURN NEW;
END
$$;

COMMENT ON FUNCTION public.resolve_inventory_linked_asset_node_ids() IS
  'Phase 5a auto-bridge: resolves inventory_items.linked_asset_node_ids (uuid[]) from linked_asset_ids (text[]) via asset_nodes.legacy_asset_id on every INSERT/UPDATE.';

DROP TRIGGER IF EXISTS trg_resolve_inventory_linked_asset_node_ids ON public.inventory_items;

CREATE TRIGGER trg_resolve_inventory_linked_asset_node_ids
BEFORE INSERT OR UPDATE OF linked_asset_ids, hive_id, linked_asset_node_ids
ON public.inventory_items
FOR EACH ROW
EXECUTE FUNCTION public.resolve_inventory_linked_asset_node_ids();

-- GIN index so readers can ask "give me inventory linked to this asset_node"
-- with O(log n) lookup; same shape the legacy linked_asset_ids GIN already
-- offers if one exists.
CREATE INDEX IF NOT EXISTS idx_inventory_linked_asset_node_ids
  ON public.inventory_items USING GIN (linked_asset_node_ids);

-- ── 3. Audit row so we can see the backfill outcome in automation_log ───────

DO $$
DECLARE
  cnt_logbook_total      bigint;
  cnt_logbook_resolved   bigint;
  cnt_logbook_unresolved bigint;
  cnt_inv_total          bigint;
  cnt_inv_resolved       bigint;
BEGIN
  SELECT count(*) INTO cnt_logbook_total
    FROM public.logbook WHERE asset_ref_id IS NOT NULL AND hive_id IS NOT NULL;
  SELECT count(*) INTO cnt_logbook_resolved
    FROM public.logbook WHERE asset_node_id IS NOT NULL;
  SELECT count(*) INTO cnt_logbook_unresolved
    FROM public.logbook
    WHERE asset_ref_id IS NOT NULL AND hive_id IS NOT NULL AND asset_node_id IS NULL;

  SELECT count(*) INTO cnt_inv_total
    FROM public.inventory_items
    WHERE hive_id IS NOT NULL
      AND linked_asset_ids IS NOT NULL
      AND array_length(linked_asset_ids, 1) > 0;
  SELECT count(*) INTO cnt_inv_resolved
    FROM public.inventory_items
    WHERE array_length(linked_asset_node_ids, 1) > 0;

  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'automation_log') THEN
    INSERT INTO public.automation_log (job_name, status, detail)
    VALUES (
      'phase_5a_asset_uuid_bridges',
      CASE WHEN cnt_logbook_unresolved = 0 THEN 'success' ELSE 'partial' END,
      format(
        'logbook: %s/%s resolved (%s unresolved); inventory_items: %s/%s with uuid array',
        cnt_logbook_resolved, cnt_logbook_total, cnt_logbook_unresolved,
        cnt_inv_resolved, cnt_inv_total
      )
    );
  END IF;
END
$$;

COMMIT;
