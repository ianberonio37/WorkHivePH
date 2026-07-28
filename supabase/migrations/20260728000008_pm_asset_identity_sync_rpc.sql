-- ─────────────────────────────────────────────────────────────────────────────
-- Let the DATABASE perform the asset-identity propagation, so pm_assets can be write-gated.
--
-- FOUND BY THE PM3 WALK (2026-07-28, PM_DEEPWALK_EXPANSION_ROADMAP):
-- pm-scheduler gates "Edit Asset" to supervisors in the CLIENT ("Supervisors only.") while
-- `pm_assets_write`'s USING is satisfied by ANY active member. Probed live: a WORKER renamed a
-- supervisor's asset to 'HIJACKED' and set its criticality to Low — one row, no error. Criticality
-- drives risk scoring, triage order and alert severity, and asset_name is how everyone identifies
-- the machine, so this is the same UI-only-gate class as the PM12 delete hole.
--
-- WHY THE OBVIOUS FIX WOULD HAVE BROKEN THE PLATFORM, measured before shipping it:
-- the natural rule ("supervisor OR the pm_asset's author", mirroring the delete guard) would also
-- refuse `syncToPMAssets` in logbook.html, which propagates an asset rename from asset_nodes into
-- pm_assets. Measured: of 90 pm_asset<->node pairs, **90** have a node author different from the
-- pm_asset author, and in **all 90** that node author is not a supervisor. So every rename on the
-- platform would have silently matched 0 rows — and a 0-row UPDATE is not an error, so
-- syncToPMAssets' `if (error)` warning would never fire. The name would diverge between asset_nodes
-- and pm_assets: a cross-surface identity split, which is the exact class this platform has spent
-- several arcs closing.
--
-- THE FIX: the propagation is a legitimate SYSTEM action, not a user write, so the database performs
-- it. This SECURITY DEFINER function renames matching pm_assets rows after checking that the caller
-- is an active member of the hive that owns them — the same reach the propagation always had, now
-- expressed where it can be enforced, and narrowed to the identity columns (asset_name, tag_id).
-- It CANNOT touch criticality, category or anything else, so it is not a back door around the
-- supervisor gate that migration 20260728000009 will add for direct edits.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.sync_pm_asset_identity(
  p_old_tag  text,
  p_new_tag  text DEFAULT NULL,
  p_new_name text DEFAULT NULL
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_rows integer := 0;
BEGIN
  IF p_old_tag IS NULL OR (p_new_tag IS NULL AND p_new_name IS NULL) THEN
    RETURN 0;
  END IF;

  -- Only rows in a hive the caller actively belongs to. auth.uid() IS NULL means a server-to-server
  -- caller (service_role / psql / the seeders), which keeps its existing reach.
  WITH updated AS (
    UPDATE public.pm_assets pa
       SET asset_name = COALESCE(p_new_name, pa.asset_name),
           tag_id     = COALESCE(p_new_tag,  pa.tag_id)
     WHERE pa.tag_id = p_old_tag
       AND (
             auth.uid() IS NULL
             OR EXISTS (
               SELECT 1 FROM public.hive_members hm
                WHERE hm.hive_id  = pa.hive_id
                  AND hm.auth_uid = auth.uid()
                  AND hm.status   = 'active'
             )
           )
    RETURNING 1
  )
  SELECT count(*) INTO v_rows FROM updated;

  RETURN v_rows;
END;
$function$;

REVOKE ALL ON FUNCTION public.sync_pm_asset_identity(text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.sync_pm_asset_identity(text, text, text) TO authenticated, service_role;
