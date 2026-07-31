-- 20260731000018_dispute_adjustment_never_deletion.sql
--
-- P4 (M1). Failure mode 4 of the sustainability study: "a settled job that is later disputed has already
-- minted cashback and debited commission." Reading the guard showed the situation is worse than the study
-- assumed - `disputed` was reachable only from `in_progress` or `completed`, so a SETTLED job could not be
-- disputed AT ALL. The money became final the instant the client released, and bad work discovered a day
-- later had no path at all: not a bad reversal, no reversal.
--
-- TWO PARTS:
--   1. settled -> disputed becomes a legal transition for the two parties (nobody else).
--   2. `apply_dispute_adjustment()` writes COMPENSATING entries. Never a DELETE, never an UPDATE - the
--      ledger is the audit trail, and a deleted row is a lie about what happened. Reversing by writing the
--      opposite entry keeps both facts: the charge happened, and it was refunded.
--
-- THE CLAWBACK DECISION, made explicitly rather than by accident. Reversing commission is easy (credit the
-- provider back what was debited). Clawing back the consumer's cashback is NOT, because they may already
-- have spent it. Three options were available: force the balance negative, refuse the dispute, or claw back
-- only what remains. This claws back ONLY WHAT THEY STILL HOLD, because:
--   - forcing a negative consumer balance breaks the invariant `validate_credit_solvency.py` enforces, and
--     that gate is right: a consumer only ever receives and spends cashback, so a negative balance means
--     credits were spent that were never minted;
--   - the consumer spent those credits in good faith on a job the platform told them was complete;
--   - the shortfall is real and is recorded in the note, so it is visible rather than absorbed.
-- The platform eats the difference. That is the honest cost of having minted cashback before the dispute
-- window closed, and it is an argument for a settlement hold later - noted, not silently borne.

-- ---------------------------------------------------------------------------------------------------
-- 1. A SETTLED JOB CAN BE DISPUTED
-- ---------------------------------------------------------------------------------------------------
-- Surgery on the complete definition, asserted. `guard_service_request_status` is long and is one of the
-- four mutation-scored guards; retyping it is how a rule gets silently dropped (this repo has paid for that
-- once already, rebuilding a function from three truncated prosrc reads and losing a cast and a clause).
do $mig$
declare
  v_def  text;
  v_new  text;
  v_from constant text := 'old.status in (''in_progress'',''completed'')';
  v_to   constant text := 'old.status in (''in_progress'',''completed'',''settled'')';
begin
  select pg_get_functiondef(oid) into v_def
    from pg_proc where proname = 'guard_service_request_status' limit 1;
  if v_def is null then
    raise exception 'guard_service_request_status not found';
  end if;
  if position(v_to in v_def) > 0 then
    raise notice 'settled -> disputed already legal - no change';
    return;
  end if;
  if position(v_from in v_def) = 0 then
    raise exception 'the dispute-origin clause was not found; refusing to guess at this guard';
  end if;
  -- The anchor was verified to occur exactly ONCE before this migration was written; replace() would
  -- otherwise silently widen more transitions than intended.
  if (length(v_def) - length(replace(v_def, v_from, ''))) / length(v_from) <> 1 then
    raise exception 'the dispute-origin clause is not unique; refusing a blind replace';
  end if;
  v_new := replace(v_def, v_from, v_to);
  execute v_new;
  raise notice 'settled -> disputed is now legal for the client and the matched provider';
end
$mig$;

-- ---------------------------------------------------------------------------------------------------
-- 2. THE COMPENSATING ENTRIES
-- ---------------------------------------------------------------------------------------------------
create or replace function public.apply_dispute_adjustment(p_request_id uuid, p_reason text default null)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
DECLARE
  r            public.service_requests%rowtype;
  v_commission numeric;
  v_cashback   numeric;
  v_held       numeric;
  v_clawback   numeric;
  v_short      numeric := 0;
BEGIN
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
$$;

revoke all on function public.apply_dispute_adjustment(uuid, text) from public, anon;
grant execute on function public.apply_dispute_adjustment(uuid, text) to authenticated;

comment on function public.apply_dispute_adjustment(uuid, text) is
  'Reverses the money on a disputed job with COMPENSATING ledger entries - never a DELETE, because the '
  'ledger is the audit trail and a deleted row is a lie. Admin-only, and never on a job the admin is a '
  'party to. Cashback is clawed back only up to what the consumer still holds; the rest is absorbed and '
  'recorded in the note rather than forced into a negative balance.';
