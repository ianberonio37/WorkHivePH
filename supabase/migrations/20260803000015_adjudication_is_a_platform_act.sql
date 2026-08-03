-- Adjudicating a dispute writes into the CLIENT's wallet, which the new transfer guard refused.
--
-- apply_dispute_adjustment() reverses commission and claws back cashback -- entries that belong to the
-- parties, written by an ADMIN who is deliberately not one of them. SECURITY DEFINER changes the
-- executing role but not the JWT, so guard_credits_non_transferable saw an admin moving credits into
-- another person's wallet and refused it. Every dispute adjudication failed.
--
-- Restated in full from pg_get_functiondef with ONE added line, rather than rewritten: the last time a
-- function here was rebuilt from a partial read it silently dropped three unrelated rules
-- ([[feedback_i_rebuilt_a_guard_from_a_partial_read]]). This function carries the admin-only check, the
-- not-your-own-job check, the already-adjusted check and the clawback clamp, and all four survive
-- untouched.

CREATE OR REPLACE FUNCTION public.apply_dispute_adjustment(p_request_id uuid, p_reason text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  r            public.service_requests%rowtype;
  v_commission numeric;
  v_cashback   numeric;
  v_held       numeric;
  v_clawback   numeric;
  v_short      numeric := 0;
BEGIN
  -- A dispute adjustment writes into the CLIENT's wallet, and SECURITY DEFINER changes the role but
  -- not the JWT, so the non-transferable guard sees an admin writing to someone else. Adjudication is a
  -- vetted platform act and says so, exactly as the listing-reward path does.
  PERFORM set_config('workhive.service_system_write','on',true);
  -- FOUNDER/ADMIN ONLY. A party to the job must not be able to reverse their own money: this platform has
  -- already shipped an admin-bypass-before-the-party-check self-deal, and the top-up queue's refusal to let
  -- an admin verify their OWN payment is the precedent being followed here.
  IF NOT public.is_marketplace_admin() THEN
    RAISE EXCEPTION 'Only a platform admin may adjust a disputed job' USING ERRCODE = '42501';
  END IF;

  SELECT * INTO r FROM public.service_requests WHERE id = p_request_id;
  IF r.id IS NULL THEN
    RAISE EXCEPTION 'Unknown request' USING ERRCODE = 'no_data_found';
  END IF;
  IF r.status <> 'disputed' THEN
    RAISE EXCEPTION 'Only a disputed job can be adjusted (this one is %)', r.status
      USING ERRCODE = 'check_violation';
  END IF;

  -- An admin must not adjust a job they are a party to, even holding the admin role. The role is for
  -- adjudicating OTHER people's disputes.
  IF r.client_auth_uid = auth.uid() THEN
    RAISE EXCEPTION 'You are the client on this job; another admin must adjudicate it'
      USING ERRCODE = '42501';
  END IF;

  -- IDEMPOTENT. Adjusting twice would refund twice.
  IF EXISTS (SELECT 1 FROM public.service_credit_ledger
              WHERE ref_id = p_request_id AND entry_type = 'adjustment') THEN
    RETURN jsonb_build_object('adjusted', false, 'reason', 'already_adjusted');
  END IF;

  SELECT -amount INTO v_commission FROM public.service_credit_ledger
   WHERE ref_id = p_request_id AND entry_type = 'commission';
  SELECT  amount INTO v_cashback   FROM public.service_credit_ledger
   WHERE ref_id = p_request_id AND entry_type = 'cashback';

  -- Reverse the commission in full: the platform did not earn it.
  IF coalesce(v_commission, 0) > 0 AND r.matched_provider_id IS NOT NULL THEN
    INSERT INTO public.service_credit_ledger
      (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
    VALUES ('provider', r.matched_provider_id, 'adjustment', v_commission, 'dispute', p_request_id,
            'Commission reversed on a disputed job' || coalesce(': ' || p_reason, ''));
  END IF;

  -- Claw back only what the consumer STILL HOLDS (see the header). Never force a negative balance.
  IF coalesce(v_cashback, 0) > 0 AND r.client_auth_uid IS NOT NULL THEN
    SELECT coalesce(sum(amount), 0) INTO v_held FROM public.service_credit_ledger
     WHERE account_type = 'consumer' AND account_id = r.client_auth_uid;
    v_clawback := least(v_cashback, greatest(v_held, 0));
    v_short    := v_cashback - v_clawback;
    IF v_clawback > 0 THEN
      INSERT INTO public.service_credit_ledger
        (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
      VALUES ('consumer', r.client_auth_uid, 'adjustment', -v_clawback, 'dispute', p_request_id,
              'Cashback clawed back on a disputed job'
              || CASE WHEN v_short > 0
                      THEN ' (' || v_short || ' already spent and absorbed by the platform)'
                      ELSE '' END
              || coalesce(': ' || p_reason, ''));
    END IF;
  END IF;

  RETURN jsonb_build_object(
    'adjusted', true,
    'commission_reversed', coalesce(v_commission, 0),
    'cashback_clawed_back', coalesce(v_clawback, 0),
    'cashback_absorbed', v_short);
END
$function$;
