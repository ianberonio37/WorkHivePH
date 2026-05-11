-- Data Retention / Right-to-Erasure -- closes PRODUCTION_FIXES #57
--
-- Provides `delete_worker_data(p_worker_name text)` which anonymizes
-- (rather than hard-deletes) a worker's rows across the platform. We
-- anonymize because hard-deletion would orphan audit trails + analytics.
-- Workers requesting erasure under GDPR / PDPA get their identity
-- scrubbed while platform-level metrics survive.
--
-- Service-role only (RLS-bypass). Triggered by the `/right-to-erasure`
-- workflow which a supervisor or platform-admin runs in response to a
-- formal worker request.

CREATE OR REPLACE FUNCTION public.delete_worker_data(p_worker_name text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  anon_name text := 'redacted-' || encode(gen_random_bytes(6), 'hex');
  result    jsonb := jsonb_build_object();
  n_updates integer;
BEGIN
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

  UPDATE public.assets                SET worker_name = anon_name WHERE worker_name = p_worker_name;
  GET DIAGNOSTICS n_updates = ROW_COUNT;
  result := result || jsonb_build_object('assets', n_updates);

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

  -- Audit the operation (anonymous record of what was erased)
  INSERT INTO public.hive_audit_log (action, actor, target_type, target_name, meta)
  VALUES ('right_to_erasure', 'system', 'worker_profile', anon_name,
          result || jsonb_build_object('original_name', '<redacted>'));

  RETURN result;
END;
$$;

-- Service-role only; explicitly REVOKE from public.
REVOKE EXECUTE ON FUNCTION public.delete_worker_data(text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.delete_worker_data(text) TO service_role;
