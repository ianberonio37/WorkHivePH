-- ─────────────────────────────────────────────────────────────────────────────
-- Deleting an asset node destroys its entire reliability evidence base. Record what it cost.
--
-- FOUND BY THE AH12 WALK (2026-07-28, ASSET_HUB_DEEPWALK_EXPANSION_ROADMAP):
-- measured on the worst real node, one DELETE takes 4,331 rows with it —
--
--     4  rcm_fmea_modes      the failure modes someone analysed
--     2  rcm_strategies      the maintenance decisions derived from them (via the mode FK)
--     1  weibull_fits        the fitted life distribution
--     1  pf_intervals        the P-F window that sets inspection frequency
--  4,323 sensor_readings     the condition-monitoring history every FUTURE fit would be built from
--
-- ...plus asset_embeddings and asset_edges. And nothing anywhere records that it happened.
--
-- The FK design itself is right and is NOT changed here: CASCADE for what is genuinely PART of the
-- asset (its modes, fits, readings, edges) and SET NULL for records that merely REFERENCE it and
-- stand on their own (logbook, pm_knowledge, anomaly_signals, drone_inspections) — a technician's
-- written entry survives the asset being retired, which is the same disposition PM6 verified for
-- logbook.pm_completion_id.
--
-- What was missing is the EVIDENCE. tg_guard_approval already refuses a non-supervisor deleting an
-- approved node, so the authority half is covered; this is the other half — who did it, and what it
-- cost. Same shape as trg_pm_asset_delete_audit (PM12), and the same reason it must be a BEFORE
-- trigger: after the cascade the counts no longer exist to be recorded.
--
-- The sensor_readings count is the one that matters most and is least obvious. Losing 4,323 readings
-- is not losing a number on a screen — it is losing the ability to ever re-derive a Weibull fit or a
-- P-F interval for that machine, which is precisely what AHK2 established those numbers decide.
-- ─────────────────────────────────────────────────────────────────────────────

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
     AND (OLD.hive_id IS NULL OR hm.hive_id = OLD.hive_id)
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

DROP TRIGGER IF EXISTS trg_asset_node_delete_audit ON public.asset_nodes;
CREATE TRIGGER trg_asset_node_delete_audit
  BEFORE DELETE ON public.asset_nodes
  FOR EACH ROW
  EXECUTE FUNCTION public.audit_asset_node_delete();
