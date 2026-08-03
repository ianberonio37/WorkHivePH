-- The buyer could earn credits and could never spend them.
--
-- Ian's rule has two halves: "when a buyer buys a service, when he wants to spend 10% credit, so on the
-- listing which has a pending 10% credits will be given to him, but the buyers choose to spend his credit
-- on his own, those 10% credits will be retained on the provider wallet."
--
-- The SPEND half shipped as two guards and no door. `guard_reward_exclusive` and `guard_reward_spend_cap`
-- both police `reward_spend` entries carefully -- the cap, the balance, the never-both rule -- and NOTHING
-- in the schema has ever written one. `authenticated` holds no INSERT privilege on the ledger, so a client
-- cannot write it either. Two guards defending a door that was never cut: the credits went in and stayed.
--
-- This is the "built but never called" shape, and it is invisible to every test that checks the guards
-- work, because the guards do work. What no test asked was whether anything reaches them.

-- ── the door ────────────────────────────────────────────────────────────────────────────────────────
create or replace function public.apply_credits_to_request(p_request uuid, p_amount numeric)
returns numeric
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare r public.service_requests%rowtype; v_uid uuid := auth.uid();
begin
  select * into r from public.service_requests where id = p_request;
  if r.id is null then
    raise exception 'That job does not exist' using errcode = 'no_data_found';
  end if;

  -- Only the buyer spends the buyer's credits. SECURITY DEFINER changes the executing ROLE and not the
  -- JWT, so auth.uid() here is still whoever pressed the button -- which is exactly what makes this check
  -- meaningful, and exactly what made three guards in this arc refuse their own platform writes.
  if v_uid is null or r.client_auth_uid is distinct from v_uid then
    raise exception 'Only the client on this job can apply their credits to it'
      using errcode = '42501';
  end if;

  if p_amount is null or p_amount <= 0 then
    raise exception 'Enter how many credits to apply' using errcode = 'check_violation';
  end if;

  -- Deliberately does NOT re-check the cap or the balance. guard_reward_spend_cap already holds both, and
  -- its messages name the actual figures ("Credits may cover at most 10% of a purchase (PHP180 here)").
  -- A second copy here would be a second thing to keep in step, and the copy that drifts is always the one
  -- the user reads. The ledger row is written as a negative amount, which is what the balance sums.
  insert into public.service_credit_ledger
    (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
  values ('consumer', v_uid, 'reward_spend', -p_amount, 'service_request', p_request,
          'credits applied to this job');

  return p_amount;
end $function$;

revoke all on function public.apply_credits_to_request(uuid, numeric) from public, anon;
grant execute on function public.apply_credits_to_request(uuid, numeric) to authenticated, service_role;

comment on function public.apply_credits_to_request(uuid, numeric) is
  'The buyer''s SPEND half of the earn-or-spend switch, and the only thing that writes a reward_spend '
  'entry. Both guards on that entry_type existed for a day with nothing able to reach them: credits could '
  'be earned and never spent.';

-- ── and the switch has to actually be a switch ──────────────────────────────────────────────────────
-- guard_reward_exclusive polices reward_earn against reward_spend, but a SERVICE request's earn side does
-- not write reward_earn -- mint_service_cashback writes 'cashback'. So a buyer who spent credits on a job
-- would still be minted cashback on the same job at settlement, and would have earned AND spent on it.
--
-- That is precisely the treadmill the exclusivity rule exists to prevent: when the reward percentage and
-- the spend cap are both 10%, a balance that earns on every job it spends on never drains, and credits
-- stop being spendable while still counting as a liability.
--
-- Minimal and reversible: cashback does not mint on a job the buyer already paid for with credits. The
-- cashback rail itself is untouched, so every job WITHOUT a spend behaves exactly as before -- checked,
-- not assumed, because three separate guards in this arc silently broke a path they did not intend to.
create or replace function public.mint_service_cashback(p_request_id uuid)
returns numeric
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $function$
DECLARE
  r        public.service_requests%rowtype;
  v_pct    numeric;
  v_base   numeric;
  v_amount numeric;
BEGIN
  SELECT * INTO r FROM public.service_requests WHERE id = p_request_id;
  IF r.id IS NULL OR r.status <> 'settled' OR r.client_auth_uid IS NULL THEN
    RETURN 0;                       -- unknown, unsettled, or no consumer to credit
  END IF;

  -- EARN OR SPEND, NEVER BOTH. A job the buyer already covered with their own credits earns nothing.
  IF EXISTS (SELECT 1 FROM public.service_credit_ledger
              WHERE ref_id = r.id AND entry_type = 'reward_spend') THEN
    RETURN 0;
  END IF;

  v_pct := public.service_knob_pct(r.hive_id, 'cashback_pct');
  IF v_pct IS NULL OR v_pct <= 0 THEN
    RETURN 0;                       -- the hive has cashback switched off
  END IF;

  -- SAME base as commission. This previously paid on `r.budget` - the client's stated budget, which is a
  -- wish rather than a transaction - so a consumer could earn cashback on a number nobody ever paid, and
  -- the platform's "net take = commission - cashback" identity did not actually hold on any job where the
  -- budget and the price differed.
  SELECT COALESCE((SELECT p.amount_paid FROM public.service_payments p WHERE p.request_id = r.id),
                  public.service_agreed_base(r.id), 0) INTO v_base;

  v_amount := round(coalesce(v_base, 0) * v_pct / 100.0, 2);
  IF v_amount <= 0 THEN
    RETURN 0;                       -- a zero-value job earns nothing; do not mint dust rows
  END IF;

  INSERT INTO public.service_credit_ledger
    (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
  VALUES ('consumer', r.client_auth_uid, 'cashback', v_amount, 'service_request', r.id,
          v_pct || '% cashback on a settled service request')
  ON CONFLICT DO NOTHING;           -- backed by service_credit_ledger_one_cashback_per_request

  RETURN v_amount;
END
$function$;

comment on function public.mint_service_cashback(uuid) is
  'Mints the consumer''s earn side on a settled job, on amount_paid rather than the stated budget. Returns '
  '0 on a job that already carries a reward_spend: earn-or-spend is exclusive, and cashback is the earn '
  'side for service requests, so without this the switch had no effect on the path buyers actually use.';
