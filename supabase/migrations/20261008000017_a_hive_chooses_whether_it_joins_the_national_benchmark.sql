-- ★A CONSENT WITH NO SWITCH (2026-10-08). hives.federated_benchmark_opted_in (migration 20260513000007, Phase 6D)
-- is "per-hive consent to contribute anonymised metrics to the national PH Industry Benchmarks data product.
-- Default false; supervisor toggles." Nothing let a supervisor toggle it, and nothing read it - so every hive's
-- figures fed the network benchmarks, the PH Intelligence report and the external intelligence API without it.
-- Those readers now take consenting hives only (_shared/federated-consent.ts). This is the switch.
--
-- set_federated_benchmark_opt_in(hive, on/off): only an ACTIVE SUPERVISOR of that hive may change it; it stamps
-- when and by whom, and writes one hive_audit_log row naming the decision, so a hive can always see who opted it
-- in or out. SECURITY DEFINER because hives' own UPDATE policy is not the place to widen; the membership check
-- here is the authority, and it reads auth.uid(), never a name from the caller.

CREATE OR REPLACE FUNCTION public.set_federated_benchmark_opt_in(p_hive_id uuid, p_opt_in boolean)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $function$
DECLARE
  v_actor text;
  v_was   boolean;
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Sign in to change your hive''s benchmark sharing.' USING ERRCODE = '42501';
  END IF;
  IF p_opt_in IS NULL THEN
    RAISE EXCEPTION 'Say whether the hive shares its benchmarks (on or off).' USING ERRCODE = '22023';
  END IF;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.hive_id = p_hive_id AND hm.auth_uid = auth.uid()
     AND hm.status = 'active' AND hm.role = 'supervisor'
   LIMIT 1;
  IF v_actor IS NULL THEN
    RAISE EXCEPTION 'Only a supervisor of this hive can change its benchmark sharing.' USING ERRCODE = '42501';
  END IF;

  SELECT federated_benchmark_opted_in INTO v_was FROM public.hives WHERE id = p_hive_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'This hive was not found.' USING ERRCODE = 'P0002';
  END IF;
  IF v_was IS NOT DISTINCT FROM p_opt_in THEN
    RETURN jsonb_build_object('ok', true, 'opted_in', p_opt_in, 'changed', false);
  END IF;

  UPDATE public.hives
     SET federated_benchmark_opted_in = p_opt_in,
         federated_opt_in_at          = now(),
         federated_opt_in_by          = v_actor
   WHERE id = p_hive_id;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (p_hive_id, v_actor,
          CASE WHEN p_opt_in THEN 'benchmark_sharing_on' ELSE 'benchmark_sharing_off' END,
          'hive', p_hive_id::text, NULL,
          jsonb_build_object('federated_benchmark_opted_in', p_opt_in, 'was', v_was));

  RETURN jsonb_build_object('ok', true, 'opted_in', p_opt_in, 'changed', true);
END;
$function$;

COMMENT ON FUNCTION public.set_federated_benchmark_opt_in(uuid, boolean) IS
  'A hive supervisor turns the hive''s contribution to the shared PH benchmarks on or off (hive.html). Stamps '
  'federated_opt_in_at / _by and writes a hive_audit_log row. Readers of cross-hive data use consenting hives only '
  '(_shared/federated-consent.ts).';

REVOKE EXECUTE ON FUNCTION public.set_federated_benchmark_opt_in(uuid, boolean) FROM PUBLIC, anon;
GRANT  EXECUTE ON FUNCTION public.set_federated_benchmark_opt_in(uuid, boolean) TO authenticated, service_role;
