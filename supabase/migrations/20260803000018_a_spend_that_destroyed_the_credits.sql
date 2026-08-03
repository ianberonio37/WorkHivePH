-- The spend debited the buyer and credited nobody, which quietly turned the whole economy into a revenue
-- model Ian explicitly rejected.
--
-- apply_credits_to_request wrote ONE leg: the buyer's balance went down by X and X ceased to exist.
-- Follow the money: those credits were backed 1:1 by cash the platform holds. Destroy the credits and the
-- platform keeps the cash with nothing owed against it. That is revenue, arriving as a rounding decision
-- rather than a decision -- and "I don't have to earn revenue, it is like, I hold the money I get, in a
-- form of credits exchange" is the sentence the entire design is built on.
--
-- It also contradicts the circuit itself. The plan's own picture has credits landing as the PROVIDER's
-- available balance and funding that provider's next listing without a new top-up. A spend is a TRANSFER,
-- not a burn: the buyer pays part of the price in credits, and the provider receives exactly those
-- credits and can spend them on their own reservations. Cash enters once at the top and never leaves;
-- the credits go round.
--
-- Why this was easy to miss: every guard passed. The cap guard checks the buyer's side, the exclusivity
-- guard checks the pair, the balance check checks the buyer -- and a missing counterparty leg violates
-- none of them. Nothing in the schema said the ledger must balance across a transaction, so a
-- single-sided entry looked exactly like a correct one.

create or replace function public.apply_credits_to_request(p_request uuid, p_amount numeric)
returns numeric
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare
  r public.service_requests%rowtype;
  v_uid uuid := auth.uid();
  v_provider uuid;
begin
  select * into r from public.service_requests where id = p_request;
  if r.id is null then
    raise exception 'That job does not exist' using errcode = 'no_data_found';
  end if;

  -- Only the buyer spends the buyer's credits. SECURITY DEFINER changes the executing ROLE and not the
  -- JWT, so auth.uid() here is still whoever pressed the button.
  if v_uid is null or r.client_auth_uid is distinct from v_uid then
    raise exception 'Only the client on this job can apply their credits to it'
      using errcode = '42501';
  end if;

  if p_amount is null or p_amount <= 0 then
    raise exception 'Enter how many credits to apply' using errcode = 'check_violation';
  end if;

  select p.auth_uid into v_provider
    from public.service_providers p where p.id = r.matched_provider_id;

  -- A spend with no counterparty would be a burn, so it is refused rather than silently written. A job
  -- with no matched provider has nobody to pay, which means there is nothing to pay FOR yet.
  if v_provider is null then
    raise exception 'This job has no provider yet, so there is nobody to pay with credits'
      using errcode = 'check_violation';
  end if;

  -- You cannot buy from yourself. Found by a probe that picked the one seeded job where the client and
  -- the matched provider are the same person: both legs landed in one wallet, netted to zero, and the
  -- call reported success. Harmless-looking, but it consumes the job's single reward_spend slot, which
  -- is what suppresses the cashback -- so a buyer could silently destroy their own earn by "paying"
  -- themselves nothing. The platform refuses self-review elsewhere for the same reason.
  if v_provider = v_uid then
    raise exception 'You cannot pay yourself in credits for your own job'
      using errcode = 'check_violation';
  end if;

  -- A vetted platform act: the second leg writes into the PROVIDER's wallet, and
  -- guard_credits_non_transferable would otherwise refuse it as a user-to-user transfer -- correctly, in
  -- every other circumstance. Announcing it is how a legitimate movement is distinguished from a gift.
  perform set_config('workhive.service_system_write', 'on', true);

  -- The buyer's side. reward_spend is what the cap and exclusivity guards police, so it stays the buyer's
  -- entry type and keeps its meaning.
  insert into public.service_credit_ledger
    (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
  values ('consumer', v_uid, 'reward_spend', -p_amount, 'service_request', p_request,
          'credits applied to this job');

  -- The provider's side. reward_fund is the counterparty leg the listing sale already uses (there with a
  -- negative amount, because there the seller FUNDS the reward; here positive, because the provider
  -- RECEIVES it). Deliberately not reward_earn: guard_reward_exclusive refuses reward_earn and
  -- reward_spend on the same job, and it is right to -- that rule is about the BUYER earning and spending
  -- on one job, and using it here would have made every credit payment impossible.
  insert into public.service_credit_ledger
    (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
  values ('consumer', v_provider, 'reward_fund', p_amount, 'service_request', p_request,
          'paid in credits by the client');

  perform set_config('workhive.service_system_write', 'off', true);

  return p_amount;
end $function$;

comment on function public.apply_credits_to_request(uuid, numeric) is
  'Moves credits from the buyer to the matched provider as part-payment for a job: TWO legs, because a '
  'single-sided spend destroys the credits and lets the platform keep the cash that backed them, which is '
  'revenue by accident. Refuses a job with no provider rather than writing a burn.';
