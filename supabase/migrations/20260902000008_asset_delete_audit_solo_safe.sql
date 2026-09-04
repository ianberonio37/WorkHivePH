-- VEHICLE SEED M6 (2026-09-02): a SOLO asset node could never be deleted.
--
-- Found live on the VM1 walk's undo: audit_asset_node_delete() (BEFORE DELETE) inserts into
-- hive_audit_log with OLD.hive_id, and hive_audit_log.hive_id is NOT NULL — so every delete of
-- a hive-less node aborts ("null value in column hive_id"), and the surviving node then
-- FK-blocks deleting its pm_asset. The wizard's "Undo — remove everything" silently left the
-- vehicle + schedule parent behind (the rollback's per-step catch swallowed it).
--
-- The audit trail is HIVE-scoped by design: its audience is the hive's supervisors. A solo
-- owner deleting their own car has no hive audience — skip the audit row (and the child
-- counts, which exist only to inform that audience), keep everything else identical.

CREATE OR REPLACE FUNCTION public.audit_asset_node_delete()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor      text;
  v_fmea       integer;
  v_strategies integer;
  v_weibull    integer;
  v_pf         integer;
  v_readings   integer;
  v_logbook    integer;
BEGIN
  -- SOLO lane (2026-09-02): hive_audit_log.hive_id is NOT NULL and its audience is the hive.
  -- A hive-less node has neither — auditing would abort the delete itself.
  IF OLD.hive_id IS NULL THEN
    RETURN OLD;
  END IF;

  -- BEFORE DELETE: the cascade has not run, so the children are still countable. After the
  -- statement completes none of this can be reconstructed.
  SELECT count(*) INTO v_fmea       FROM public.rcm_fmea_modes WHERE asset_id = OLD.id;
  SELECT count(*) INTO v_strategies FROM public.rcm_strategies s
    JOIN public.rcm_fmea_modes f ON f.id = s.fmea_mode_id WHERE f.asset_id = OLD.id;
  SELECT count(*) INTO v_weibull    FROM public.weibull_fits  WHERE asset_id = OLD.id;
  SELECT count(*) INTO v_pf         FROM public.pf_intervals  WHERE asset_id = OLD.id;
  SELECT count(*) INTO v_readings   FROM public.sensor_readings WHERE asset_id = OLD.id;
  -- SET NULL rather than CASCADE — these SURVIVE, but they lose their link to the asset, so the
  -- count is worth recording as "orphaned", not "destroyed".
  SELECT count(*) INTO v_logbook    FROM public.logbook WHERE asset_node_id = OLD.id;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
     AND hm.hive_id = OLD.hive_id
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    OLD.hive_id,
    COALESCE(v_actor, OLD.worker_name, 'unknown'),
    'delete_asset_node',
    'asset_nodes',
    OLD.id::text,
    COALESCE(OLD.tag, OLD.name, '(unnamed asset)'),
    jsonb_build_object(
      'status_was',            OLD.status,
      'criticality',           OLD.criticality,
      'fmea_modes_destroyed',  v_fmea,
      'rcm_strategies_destroyed', v_strategies,
      'weibull_fits_destroyed',   v_weibull,
      'pf_intervals_destroyed',   v_pf,
      -- The evidence base. Without these no future fit for this machine is derivable.
      'sensor_readings_destroyed', v_readings,
      'logbook_entries_orphaned',  v_logbook,
      'source',                'db_trigger'
    )
  );

  RETURN OLD;
END;
$function$;
