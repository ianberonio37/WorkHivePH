-- ─────────────────────────────────────────────────────────────────────────────
-- Move asset-hub's lazy pm_asset creation into the DATABASE, so pm_assets INSERT can be gated.
--
-- THE THIRD VERB (PM2 walk, 2026-07-28). pm-scheduler's goAddAsset() is supervisor-gated in the
-- page, but a WORKER inserting a pm_asset into their own hive succeeds at the database — probed,
-- 1 row. PM12 closed DELETE (20260728000006) and PM3 closed UPDATE (20260728000009); INSERT was the
-- one left. Lower severity than the other two — the row lands in the member's OWN hive and is
-- self-authored, so it is not a cross-tenant hole — but it lets someone the UI says cannot add
-- assets move their hive's PM compliance DENOMINATOR.
--
-- WHY THE GUARD COULD NOT SHIP ALONE, measured rather than assumed: asset-hub's resolvePmAssetId()
-- LAZILY CREATES a pm_assets row when an approved RCM strategy is pushed to the PM Scheduler, with
-- no role gate of its own. A supervisor-only INSERT rule would have broken that flow for every
-- worker using RCM — the same shape as the PM3 trap, where the naive rule would have silently
-- stopped all 90 asset renames.
--
-- So the creation becomes what it always was: a SYSTEM action derived from an asset_node the
-- database already holds. Moving it here is strictly SAFER than the client insert it replaces —
-- every field is read from the node server-side, so a caller can no longer choose the new asset's
-- name, category or criticality, and the membership check happens where the write lands.
--
-- Mirrors the whole client function, including its lookup-then-create order and the node back-link,
-- so asset-hub keeps one round trip and cannot drift from it.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.ensure_pm_asset_for_node(p_node_id uuid)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_node   public.asset_nodes%ROWTYPE;
  v_target text;
  v_id     uuid;
BEGIN
  SELECT * INTO v_node FROM public.asset_nodes WHERE id = p_node_id;
  IF NOT FOUND THEN
    RETURN NULL;
  END IF;

  -- Caller must be an active member of the node's hive. auth.uid() IS NULL = server-to-server.
  IF auth.uid() IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM public.hive_members hm
        WHERE hm.hive_id  = v_node.hive_id
          AND hm.auth_uid = auth.uid()
          AND hm.status   = 'active'
     ) THEN
    RAISE EXCEPTION 'ensure_pm_asset_for_node: caller is not an active member of that hive'
      USING ERRCODE = '42501';
  END IF;

  IF v_node.pm_asset_id IS NOT NULL THEN
    RETURN v_node.pm_asset_id;
  END IF;

  v_target := NULLIF(btrim(COALESCE(v_node.tag, v_node.name, '')), '');

  -- Prefer an existing asset with the same name in the same hive, and link the node to it.
  IF v_target IS NOT NULL THEN
    SELECT pa.id INTO v_id
      FROM public.pm_assets pa
     WHERE pa.hive_id = v_node.hive_id
       AND pa.asset_name = v_target
     LIMIT 1;
  END IF;

  -- Otherwise create one FROM THE NODE. Every value is read here, not supplied by the caller.
  IF v_id IS NULL THEN
    INSERT INTO public.pm_assets
      (hive_id, worker_name, auth_uid, asset_name, tag_id, location, category, criticality)
    VALUES
      (v_node.hive_id,
       COALESCE(v_node.worker_name, 'system'),
       v_node.auth_uid,
       COALESCE(v_target, 'Untitled asset'),
       v_node.tag,
       v_node.location,
       COALESCE(v_node.iso_class, 'Other'),
       COALESCE(v_node.criticality, 'Major'))
    RETURNING id INTO v_id;
  END IF;

  UPDATE public.asset_nodes SET pm_asset_id = v_id
   WHERE id = p_node_id AND hive_id = v_node.hive_id;

  RETURN v_id;
END;
$function$;

REVOKE ALL ON FUNCTION public.ensure_pm_asset_for_node(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.ensure_pm_asset_for_node(uuid) TO authenticated, service_role;
