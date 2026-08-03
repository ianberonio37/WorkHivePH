-- A buyer could pay part of a job in credits, win the dispute, and never get those credits back.
--
-- apply_dispute_adjustment already unwinds the two money legs it knew about when it was written:
--
--     commission  -> reversed in full        (the platform did not earn it)
--     cashback    -> clawed back, bounded by what the consumer still holds
--
-- It predates the credit economy, so it has never heard of the pair that apply_credits_to_request
-- writes:
--
--     reward_spend  -X on the BUYER      (they paid with it)
--     reward_fund   +X on the PROVIDER   (they received it)
--
-- So on a disputed job the commission came back, the cashback came back, and the PHP550 the buyer
-- actually handed over in credits stayed with the provider. The buyer paid for a job that was
-- adjudicated as disputed and was out of pocket for the credit portion of it, silently - no error, no
-- entry, nothing to notice.
--
-- Worth saying plainly why this is the platform's job at all, since the platform holds no money: the
-- PESO half of a refund is between the buyer and the provider directly and WorkHive cannot and should
-- not touch it. The CREDIT half is different - it lives on this ledger, the platform is the only party
-- that can move it, and refusing to would mean the one portion of the payment we DO control is the one
-- portion that never comes back.
--
-- SAME DISCIPLINE AS THE CASHBACK CLAWBACK, deliberately: claw back only what the provider STILL HOLDS
-- and say so when it falls short, rather than forcing a negative balance. A provider who has already
-- spent those credits on their own listings is not made insolvent by an adjudication; the shortfall is
-- absorbed and recorded, exactly as the cashback path already does for a consumer.

create or replace function public.apply_dispute_adjustment(p_request_id uuid, p_reason text default null::text)
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $function$
DECLARE
  r            public.service_requests%rowtype;
  v_commission numeric;
  v_cashback   numeric;
  v_held       numeric;
  v_clawback   numeric;
  v_short      numeric := 0;
  v_spent      numeric;
  v_prov_uid   uuid;
  v_prov_held  numeric;
  v_prov_back  numeric;
  v_prov_short numeric := 0;
BEGIN
  PERFORM set_config('workhive.service_system_write','on',true);
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
  IF r.client_auth_uid = auth.uid() THEN
    RAISE EXCEPTION 'You are the client on this job; another admin must adjudicate it'
      USING ERRCODE = '42501';
  END IF;

  -- IDEMPOTENT. Adjusting twice would refund twice. Covers the credit legs below too, because they are
  -- written as 'adjustment' on the same ref_id.
  IF EXISTS (SELECT 1 FROM public.service_credit_ledger
              WHERE ref_id = p_request_id AND entry_type = 'adjustment') THEN
    RETURN jsonb_build_object('adjusted', false, 'reason', 'already_adjusted');
  END IF;

  SELECT -amount INTO v_commission FROM public.service_credit_ledger
   WHERE ref_id = p_request_id AND entry_type = 'commission';
  SELECT  amount INTO v_cashback   FROM public.service_credit_ledger
   WHERE ref_id = p_request_id AND entry_type = 'cashback';
  -- what the buyer actually PAID in credits (stored negative on their side)
  SELECT -amount INTO v_spent      FROM public.service_credit_ledger
   WHERE ref_id = p_request_id AND entry_type = 'reward_spend';

  -- Reverse the commission in full: the platform did not earn it.
  IF coalesce(v_commission, 0) > 0 AND r.matched_provider_id IS NOT NULL THEN
    INSERT INTO public.service_credit_ledger
      (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
    VALUES ('provider', r.matched_provider_id, 'adjustment', v_commission, 'dispute', p_request_id,
            'Commission reversed on a disputed job' || coalesce(': ' || p_reason, ''));
  END IF;

  -- Claw back only what the consumer STILL HOLDS. Never force a negative balance.
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

  -- ── THE CREDIT PAYMENT ITSELF, which this function never used to know about ─────────────────────────
  -- Return to the buyer what they paid, and take it back from the provider who received it - bounded by
  -- what that provider still holds, so an adjudication cannot make them insolvent.
  IF coalesce(v_spent, 0) > 0 AND r.client_auth_uid IS NOT NULL THEN
    SELECT p.auth_uid INTO v_prov_uid
      FROM public.service_providers p WHERE p.id = r.matched_provider_id;

    IF v_prov_uid IS NOT NULL THEN
      SELECT coalesce(sum(amount), 0) INTO v_prov_held FROM public.service_credit_ledger
       WHERE account_type = 'consumer' AND account_id = v_prov_uid;
      v_prov_back  := least(v_spent, greatest(v_prov_held, 0));
      v_prov_short := v_spent - v_prov_back;

      IF v_prov_back > 0 THEN
        INSERT INTO public.service_credit_ledger
          (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
        VALUES ('consumer', v_prov_uid, 'adjustment', -v_prov_back, 'dispute', p_request_id,
                'Credit payment returned to the buyer on a disputed job'
                || coalesce(': ' || p_reason, ''));
      END IF;
    ELSE
      v_prov_back := 0; v_prov_short := v_spent;
    END IF;

    -- The buyer is made whole for the FULL amount they paid. Any shortfall on the provider's side is the
    -- platform's to absorb, not the buyer's to eat: they paid, and the adjudication went their way.
    INSERT INTO public.service_credit_ledger
      (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
    VALUES ('consumer', r.client_auth_uid, 'adjustment', v_spent, 'dispute', p_request_id,
            'Credits you paid on this job, returned'
            || CASE WHEN v_prov_short > 0
                    THEN ' (' || v_prov_short || ' could not be recovered from the provider and was '
                         || 'absorbed by the platform)'
                    ELSE '' END
            || coalesce(': ' || p_reason, ''));
  END IF;

  RETURN jsonb_build_object(
    'adjusted', true,
    'commission_reversed', coalesce(v_commission, 0),
    'cashback_clawed_back', coalesce(v_clawback, 0),
    'cashback_shortfall', v_short,
    'credits_returned_to_buyer', coalesce(v_spent, 0),
    'credits_recovered_from_provider', coalesce(v_prov_back, 0),
    'provider_shortfall', v_prov_short
  );
END $function$;

comment on function public.apply_dispute_adjustment(uuid, text) is
  'Unwinds a disputed job''s money: commission reversed in full, cashback clawed back, and - since '
  '20260803000029 - the CREDIT PAYMENT returned to the buyer and recovered from the provider. Before '
  'that, a buyer who paid part of a job in credits and won the dispute never saw those credits again: '
  'the function predated the credit economy and knew only about commission and cashback. Both clawbacks '
  'are bounded by what the counterparty still holds, so an adjudication never forces a negative balance; '
  'the buyer is made whole regardless and any shortfall is recorded as absorbed by the platform.';
