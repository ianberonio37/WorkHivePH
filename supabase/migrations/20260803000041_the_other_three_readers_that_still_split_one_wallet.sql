-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- THE OTHER THREE READERS THAT STILL SPLIT ONE PERSON'S WALLET IN TWO
--
-- mig 39 established the rule: a person has ONE wallet. Credits reach the ledger under two account
-- namespaces — ('consumer', auth_uid) when someone earns or spends as a buyer, and ('provider',
-- provider_id) when a provider tops up — and both belong to the same human. mig 39 repointed the
-- three readers it found (guard_accept_requires_reservation, seller_credit_balance,
-- provider_credit_balance) at person_credit_balance().
--
-- It missed three more. Found 2026-08-03 walking the owed live-MCP scenario
-- `LM-R-money-lifecycle-spend-chosen`.
--
--   1. guard_reward_spend_cap  — the balance check behind EVERY credit payment
--   2. my_credit_balance()     — what the buyer's own screen reads
--   3. apply_dispute_adjustment — the bound on what an adjudication can recover
--
-- MEASURED, on live data: every credit in this economy currently sits in the PROVIDER namespace
-- (three provider accounts hold it; there is not one consumer row). So:
--
--   job price       = 800.00      (10% cap = 80)
--   person OWNS     = 340.00      via person_credit_balance()
--   the guard SEES  = 0           via its own single-namespace sum
--   spending 80     -> REFUSED 23514 "Not enough credits: balance is PHP0, this would spend PHP80."
--
-- That is not an edge case, it is the whole feature: with all credits in the provider namespace,
-- NO buyer can spend credits at all. The "spend" half of the earn-or-spend switch — the thing the
-- 10% reward exists to fund — has never been able to fire. And the refusal is the cruellest shape a
-- money error takes: it tells someone holding PHP340 that their balance is zero.
--
-- my_credit_balance() is the same bug one layer up: the confirm sheet asks it what the buyer can
-- spend, so a provider-turned-buyer is shown no spend field at all and never even reaches the
-- refusal. The screen and the guard agree, and both are wrong.
--
-- apply_dispute_adjustment is quieter but costs real money. It bounds recovery by "what that
-- provider STILL HOLDS", reading only ('consumer', provider_uid) — which is empty for a provider
-- who holds credits in their provider account. The buyer is still made whole, so nothing looks
-- broken; the difference is silently booked as a shortfall the PLATFORM absorbs, while the provider
-- keeps credits the adjudication decided they should return.
--
-- THE FIX: all three read the person's whole wallet. No ledger row moves — the ledger is
-- append-only and its history is correct. Only the readers change, exactly as mig 39 did.
--
-- A NOTE ON NEGATIVE NAMESPACE BALANCES, because this is the part that looks alarming and is not:
-- a buyer spending from ('consumer', uid) while their credits sit in ('provider', id) drives the
-- consumer namespace negative while the PERSON stays positive. That is the mig 39 model working as
-- designed — a namespace is a bookkeeping location, not a wallet. The invariant that matters, and
-- the one these guards enforce, is that the PERSON never goes below zero.
-- ═══════════════════════════════════════════════════════════════════════════════════════════════

-- ── 1. The spend guard ─────────────────────────────────────────────────────────────────────────
create or replace function public.guard_reward_spend_cap()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_price numeric; v_hive uuid; v_cap numeric; v_bal numeric; v_uid uuid;
begin
  if new.entry_type <> 'reward_spend' then return new; end if;

  select r.hive_id into v_hive from public.service_requests r where r.id = new.ref_id;
  if not found then return new; end if;            -- not a service job at all (e.g. a listing ref)

  v_price := public.service_request_price(new.ref_id);

  if coalesce(v_price, 0) <= 0 then
    raise exception 'This job has no agreed price yet, so there is no 10%% of it to pay in credits. '
                    'Agree a price with the provider first.'
      using errcode = 'check_violation';
  end if;

  v_cap := round(v_price * public.service_knob_pct(v_hive,'reward_spend_cap_pct') / 100.0, 2);
  if abs(new.amount) > v_cap + 0.005 then
    raise exception 'Credits may cover at most % of a purchase (PHP% here); this would apply PHP%.',
                    to_char(public.service_knob_pct(v_hive,'reward_spend_cap_pct'),'FM990') || '%',
                    to_char(v_cap,'FM999G999G990'), to_char(abs(new.amount),'FM999G999G990')
      using errcode = 'check_violation';
  end if;

  -- ONE PERSON, ONE WALLET (mig 41). This previously summed only the row's own namespace, so a
  -- provider who topped up and then hired someone was told "balance is PHP0" while holding PHP340.
  -- Resolve the HUMAN behind the account, then ask what that human owns across both namespaces.
  v_uid := case
             when new.account_type = 'consumer' then new.account_id
             when new.account_type = 'provider' then
               (select sp.auth_uid from public.service_providers sp where sp.id = new.account_id)
           end;

  if v_uid is not null then
    v_bal := public.person_credit_balance(v_uid);
  else
    -- A provider account with no auth_uid belongs to no one who can sign in (hive-owned rows).
    -- There is no person to aggregate, so the namespace sum IS the whole truth for it.
    select coalesce(sum(amount),0) into v_bal from public.service_credit_ledger
     where account_type = new.account_type and account_id = new.account_id;
  end if;

  if v_bal + new.amount < -0.005 then
    raise exception 'Not enough credits: balance is PHP%, this would spend PHP%.',
                    to_char(v_bal,'FM999G999G990'), to_char(abs(new.amount),'FM999G999G990')
      using errcode = 'check_violation';
  end if;
  return new;
end $function$;

comment on function public.guard_reward_spend_cap() is
  'Bounds a reward_spend by the hive cap (10% of the job price) AND by what the PERSON holds across '
  'both ledger namespaces (mig 41 — it read one namespace and refused every real spend, because all '
  'credits currently sit provider-side). A namespace may go negative; the person may not.';

-- ── 2. What the buyer's own screen reads ───────────────────────────────────────────────────────
create or replace function public.my_credit_balance()
returns numeric
language sql
stable security definer
set search_path to 'pg_catalog', 'public'
as $function$
  -- mig 41: was `sum(amount) where account_type='consumer' and account_id=auth.uid()`, which showed
  -- PHP0 to anyone whose credits arrived through a provider top-up — so the confirm sheet offered
  -- them no spend field at all. One wallet, one number.
  select public.person_credit_balance(auth.uid());
$function$;

comment on function public.my_credit_balance() is
  'The signed-in person''s spendable credits across BOTH ledger namespaces (mig 41). Backed by '
  'person_credit_balance so the screen and guard_reward_spend_cap can never disagree.';

-- ── 3. The bound on what an adjudication can recover ───────────────────────────────────────────
-- Rewritten in place: only the two balance reads change. Every other line, including the shortfall
-- accounting and the append-only compensating-entry discipline, is mig 29's and stays as it was.
do $$
declare v_src text;
begin
  select pg_get_functiondef(oid) into v_src from pg_proc where proname = 'apply_dispute_adjustment';

  -- The consumer clawback bound (cashback, now 0% but the path is still live for historical rows).
  v_src := replace(v_src,
    'SELECT coalesce(sum(amount), 0) INTO v_held FROM public.service_credit_ledger'
    || E'\n     WHERE account_type = ''consumer'' AND account_id = r.client_auth_uid;',
    'v_held := public.person_credit_balance(r.client_auth_uid);   -- mig 41: one wallet, both namespaces');

  -- The provider recovery bound — the one that costs the platform real money when it under-reads.
  v_src := replace(v_src,
    'SELECT coalesce(sum(amount), 0) INTO v_prov_held FROM public.service_credit_ledger'
    || E'\n       WHERE account_type = ''consumer'' AND account_id = v_prov_uid;',
    'v_prov_held := public.person_credit_balance(v_prov_uid);   -- mig 41: one wallet, both namespaces');

  execute v_src;
end $$;

-- Fail loudly if either replacement missed: a silent no-op here would leave the money bug in place
-- while this migration reported success, which is the exact "green while broken" shape the platform
-- keeps getting bitten by.
do $$
declare v_src text;
begin
  select prosrc into v_src from pg_proc where proname = 'apply_dispute_adjustment';
  if v_src like '%account_type = ''consumer'' AND account_id = r.client_auth_uid%'
     or v_src like '%account_type = ''consumer'' AND account_id = v_prov_uid%' then
    raise exception 'mig 41 FAILED: apply_dispute_adjustment still reads a single namespace for a balance bound';
  end if;
  if v_src not like '%person_credit_balance(r.client_auth_uid)%'
     or v_src not like '%person_credit_balance(v_prov_uid)%' then
    raise exception 'mig 41 FAILED: apply_dispute_adjustment did not pick up person_credit_balance';
  end if;
end $$;

comment on function public.apply_dispute_adjustment(uuid, text) is
  'Adjudicates a disputed job with compensating ledger entries (never a rewrite). Recovery is bounded '
  'by what each party still holds ACROSS BOTH namespaces (mig 41) — reading one namespace made the '
  'platform absorb shortfalls against providers who still held the credits.';
