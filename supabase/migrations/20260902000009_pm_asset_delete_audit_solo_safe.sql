-- VEHICLE SEED M6b (2026-09-02): the SIBLING of 20260902000008 — same bug, same fix.
-- audit_pm_asset_delete() inserts hive_audit_log(hive_id = OLD.hive_id); NOT NULL aborts every
-- solo pm_asset delete (found in the same VM1-undo walk: the node fix landed, then the pm_asset
-- delete hit the identical wall one statement later). The full class was enumerated:
-- pg_proc prosrc ~ 'hive_audit_log' + 'OLD.hive_id' → audit_asset_node_delete (fixed in 000008),
-- audit_pm_asset_delete (this file), guard_and_audit_project_removal (projects.hive_id is
-- NOT NULL — no solo lane exists there, so it is out of the class by construction).

CREATE OR REPLACE FUNCTION public.audit_pm_asset_delete()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor  text;
  v_comps  integer;
  v_scope  integer;
  v_oldest timestamptz;
BEGIN
  -- SOLO lane (2026-09-02): hive_audit_log.hive_id is NOT NULL and its audience is the hive.
  IF OLD.hive_id IS NULL THEN
    RETURN OLD;
  END IF;

  -- BEFORE DELETE: the cascade has not run yet, so the children are still countable. After the
  -- statement completes this information no longer exists anywhere.
  SELECT count(*), min(completed_at) INTO v_comps, v_oldest
    FROM public.pm_completions WHERE asset_id = OLD.id;
  SELECT count(*) INTO v_scope
    FROM public.pm_scope_items WHERE asset_id = OLD.id;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
     AND hm.hive_id = OLD.hive_id
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    OLD.hive_id,
    COALESCE(v_actor, OLD.worker_name, 'unknown'),
    'delete_pm_asset',
    'pm_assets',
    OLD.id::text,
    COALESCE(OLD.asset_name, '(unnamed asset)'),
    jsonb_build_object(
      'criticality',            OLD.criticality,
      'category',               OLD.category,
      -- What the deletion actually cost, which is the part nobody could see.
      'completions_destroyed',  v_comps,
      'scope_items_destroyed',  v_scope,
      'history_began',          v_oldest,
      'source',                 'db_trigger'
    )
  );

  RETURN OLD;
END;
$function$;
