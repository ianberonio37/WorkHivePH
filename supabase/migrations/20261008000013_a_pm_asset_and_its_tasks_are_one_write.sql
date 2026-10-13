-- ★A FAILED TASK SAVE LEFT THE ASSET ON THE SCHEDULE WITH NO SCHEDULE (2026-10-08, found authoring the UI-write
-- recipes). pm-scheduler.html saveAsset INSERTed pm_assets, then - as a second, separate request - INSERTed its
-- pm_scope_items. When the second insert was refused (a text cap, the daily row cap, a network drop) the asset
-- stayed: registered, counted on the dashboard, and carrying zero PM tasks, so nothing about it would ever come
-- due. The page did show an error for that case, and then immediately replaced it with the success toast
-- ("added -> on your PM schedule now"), so the person was told the opposite of what happened.
--
-- One function, one transaction: the asset and every one of its tasks commit together or nothing is created.
-- SECURITY INVOKER on purpose - pm_assets_insert_guard (a hive asset needs an active SUPERVISOR) and
-- pm_scope_items_write still decide, exactly as they did for the two client inserts. Attribution is pinned by
-- bind_pm_asset_submitter as before; auth_uid is the caller's, whatever the payload says.

CREATE OR REPLACE FUNCTION public.create_pm_asset_with_tasks(p_asset jsonb, p_tasks jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_asset  public.pm_assets%ROWTYPE;
  v_tasks  integer := 0;
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Sign in to add a PM asset.' USING ERRCODE = '42501';
  END IF;
  IF p_asset IS NULL OR jsonb_typeof(p_asset) <> 'object' THEN
    RAISE EXCEPTION 'The asset details are missing.' USING ERRCODE = '22023';
  END IF;
  IF p_tasks IS NOT NULL AND jsonb_typeof(p_tasks) <> 'array' THEN
    RAISE EXCEPTION 'The PM tasks must be a list.' USING ERRCODE = '22023';
  END IF;

  INSERT INTO public.pm_assets
    (hive_id, worker_name, auth_uid, asset_name, tag_id, location, category, criticality, last_anchor_date)
  VALUES
    (NULLIF(p_asset->>'hive_id', '')::uuid,
     COALESCE(NULLIF(p_asset->>'worker_name', ''), 'unknown'),
     auth.uid(),
     p_asset->>'asset_name',
     NULLIF(p_asset->>'tag_id', ''),
     NULLIF(p_asset->>'location', ''),
     p_asset->>'category',
     COALESCE(NULLIF(p_asset->>'criticality', ''), 'Major'),
     NULLIF(p_asset->>'last_anchor_date', '')::date)
  RETURNING * INTO v_asset;

  IF p_tasks IS NOT NULL AND jsonb_array_length(p_tasks) > 0 THEN
    INSERT INTO public.pm_scope_items (asset_id, hive_id, item_text, frequency, anchor_date, is_custom)
    SELECT v_asset.id, v_asset.hive_id, t->>'item_text', t->>'frequency',
           COALESCE(NULLIF(t->>'anchor_date', '')::date, v_asset.last_anchor_date),
           COALESCE((t->>'is_custom')::boolean, false)
      FROM jsonb_array_elements(p_tasks) t;
    GET DIAGNOSTICS v_tasks = ROW_COUNT;
  END IF;

  RETURN jsonb_build_object('ok', true, 'asset', to_jsonb(v_asset), 'tasks', v_tasks);
END;
$function$;

COMMENT ON FUNCTION public.create_pm_asset_with_tasks(jsonb, jsonb) IS
  'Create a PM asset and all of its scope items in ONE transaction (pm-scheduler.html saveAsset): either the '
  'asset exists with every task, or nothing was created. SECURITY INVOKER - pm_assets / pm_scope_items RLS '
  'still decide. Returns {ok, asset, tasks}.';

REVOKE ALL ON FUNCTION public.create_pm_asset_with_tasks(jsonb, jsonb) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.create_pm_asset_with_tasks(jsonb, jsonb) TO authenticated, service_role;
