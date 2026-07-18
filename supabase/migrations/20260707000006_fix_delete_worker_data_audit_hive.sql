-- 20260707000006_fix_delete_worker_data_audit_hive.sql
--
-- FIX: delete_worker_data() (GDPR/PDPA right-to-erasure) would FAIL on EVERY invocation
-- (found 2026-07-07 by the platform-wide "RPC insert omits a NOT NULL column" sweep, the
-- same class as store_memory_turn / migration 20260707000005). Its final audit write —
-- `INSERT INTO hive_audit_log (action, actor, target_type, target_name, meta)` — OMITTED
-- `hive_id`, which is NOT NULL (FK -> hives). So the audit insert threw a not-null violation
-- and, because the whole function is ONE transaction, the ENTIRE erasure ROLLED BACK: a
-- worker's data-deletion request errored and their data was NOT anonymized/deleted. A
-- silent compliance failure (the function is compliance-invoked, rarely exercised).
--
-- Root cause: hive_audit_log is HIVE-SCOPED (hive_id NOT NULL) but this erasure is CROSS-HIVE
-- (keyed only on worker_name — a worker may belong to several hives), so there is no single
-- hive_id in scope. Correct model: audit the erasure in EACH hive the worker belonged to.
-- We capture the worker's hive_ids BEFORE anonymizing hive_members, then INSERT one
-- right_to_erasure audit row per hive (all NOT NULL cols — hive_id/actor/action — set). A
-- worker with no hive membership completes the erasure with no hive_audit_log row (there is
-- no hive context to audit in), which is correct.

CREATE OR REPLACE FUNCTION public.delete_worker_data(p_worker_name text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  -- gen_random_uuid() (pg_catalog) not gen_random_bytes() (pgcrypto/extensions): pgcrypto is
  -- OUTSIDE this SECURITY DEFINER function's locked search_path ('pg_catalog','public'), so the
  -- old initializer raised "no function matches" and aborted the whole erasure before it began.
  anon_name  text := 'redacted-' || replace(gen_random_uuid()::text, '-', '');
  result     jsonb := jsonb_build_object();
  n_updates  integer;
  v_hive_ids uuid[];
BEGIN
  -- Capture the worker's hive memberships FIRST: hive_audit_log is hive-scoped (hive_id NOT
  -- NULL) but this erasure is cross-hive, so we audit it in every hive the worker belonged to.
  SELECT array_agg(DISTINCT hive_id) INTO v_hive_ids
  FROM public.hive_members
  WHERE worker_name = p_worker_name AND hive_id IS NOT NULL;

  -- Anonymize identity across user-data tables. Each UPDATE counts so
  -- callers can verify the scrub touched the expected surfaces.

  UPDATE public.logbook               SET worker_name = anon_name WHERE worker_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('logbook', n_updates);

  UPDATE public.inventory_items       SET worker_name = anon_name WHERE worker_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('inventory_items', n_updates);

  UPDATE public.inventory_transactions SET worker_name = anon_name WHERE worker_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('inventory_transactions', n_updates);

  UPDATE public.pm_completions        SET worker_name = anon_name WHERE worker_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('pm_completions', n_updates);

  -- asset_nodes, NOT the legacy `assets` table (dropped Phase 5c). The stale `UPDATE public.assets`
  -- raised "relation does not exist" and aborted the whole erasure — the THIRD 100%-fatal bug here.
  UPDATE public.asset_nodes           SET worker_name = anon_name WHERE worker_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('asset_nodes', n_updates);

  UPDATE public.pm_assets             SET worker_name = anon_name WHERE worker_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('pm_assets', n_updates);

  UPDATE public.schedule_items        SET worker_name = anon_name WHERE worker_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('schedule_items', n_updates);

  UPDATE public.skill_profiles        SET worker_name = anon_name WHERE worker_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('skill_profiles', n_updates);

  UPDATE public.skill_badges          SET worker_name = anon_name WHERE worker_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('skill_badges', n_updates);

  UPDATE public.community_posts       SET author_name = anon_name WHERE author_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('community_posts', n_updates);

  UPDATE public.community_replies     SET author_name = anon_name WHERE author_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('community_replies', n_updates);

  UPDATE public.hive_members          SET worker_name = anon_name WHERE worker_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('hive_members', n_updates);

  -- Hard-delete the worker_profiles row LAST since other tables reference
  -- worker_name (a soft FK). With auth.users cascade configured, the
  -- supabase_admin can DELETE the auth row to complete the erasure
  -- across auth + storage.
  DELETE FROM public.worker_profiles WHERE display_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('worker_profiles_deleted', n_updates);

  -- Audit the operation in EACH hive the worker belonged to (hive_audit_log.hive_id is NOT NULL).
  -- Anonymous record: the original name is never written (only the redacted anon_name).
  IF v_hive_ids IS NOT NULL THEN
    INSERT INTO public.hive_audit_log (hive_id, action, actor, target_type, target_name, meta)
    SELECT hid, 'right_to_erasure', 'system', 'worker_profile', anon_name,
           result || jsonb_build_object('original_name', '<redacted>')
    FROM unnest(v_hive_ids) AS hid;
  END IF;

  RETURN result;
END;
$function$;
