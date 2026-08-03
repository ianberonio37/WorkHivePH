-- The same wrong price, in two places, four hours apart.
--
-- guard_reward_spend_cap capped credit payments against `service_requests.budget`, and every job with a
-- matched provider has budget = NULL, so the cap silently permitted everything (fixed in ...000019). Then
-- the confirm-payment sheet computed the buyer's cap the same way, off the same NULL, and offered a
-- maximum of zero -- so the credits field never rendered and the spend half stayed unreachable from the
-- only screen where it applies.
--
-- One rule, two implementations, two bugs. The fix is not to correct the second copy: it is to stop
-- having a second copy. `service_request_price()` is now the single answer to "what does this job cost",
-- and both the guard and the UI ask it.
--
-- Order, most-agreed first. Each step is a stronger claim than the one after it:
--   amount_paid            what actually changed hands. A fact.
--   service_agreed_base()  what the two parties agreed. Already the base for commission AND cashback.
--   budget                 what the client wished for at request time. Frequently never filled in --
--                          mint_service_cashback was moved OFF it for exactly this reason, because a
--                          consumer could earn cashback "on a number nobody ever paid".

create or replace function public.service_request_price(p_request uuid)
returns numeric
language sql
stable security definer
set search_path to 'pg_catalog', 'public'
as $function$
  select coalesce(
           (select p.amount_paid from public.service_payments p where p.request_id = p_request),
           nullif(public.service_agreed_base(p_request), 0),
           (select r.budget from public.service_requests r where r.id = p_request),
           0
         );
$function$;

revoke all on function public.service_request_price(uuid) from public;
grant execute on function public.service_request_price(uuid) to authenticated, anon, service_role;

comment on function public.service_request_price(uuid) is
  'The single answer to "what does this job cost": amount_paid, else the agreed base, else the stated '
  'budget. Extracted after the same coalesce was written wrong twice - once in the spend cap (which then '
  'capped nothing, because every matched job has a NULL budget) and once in the confirm sheet (which then '
  'offered a cap of zero, so the credits field never appeared).';

-- The guard now asks rather than re-deriving.
create or replace function public.guard_reward_spend_cap()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_price numeric; v_hive uuid; v_cap numeric; v_bal numeric;
begin
  if new.entry_type <> 'reward_spend' then return new; end if;

  select r.hive_id into v_hive from public.service_requests r where r.id = new.ref_id;
  if not found then return new; end if;            -- not a service job at all (e.g. a listing ref)

  v_price := public.service_request_price(new.ref_id);

  -- "No price yet" must not read as "no limit". A job with nothing agreed has no 10% to compute.
  if coalesce(v_price, 0) <= 0 then
    raise exception 'This job has no agreed price yet, so there is no 10%% of it to pay in credits. '
                    'Agree a price with the provider first.'
      using errcode = 'check_violation';
  end if;

  v_cap := round(v_price * public.service_knob_pct(v_hive,'reward_spend_cap_pct') / 100.0, 2);
  if abs(new.amount) > v_cap + 0.005 then
    -- The percent SIGN is appended to the value inside to_char, not written as %% in the format string:
    -- PL/pgSQL resolves %%% left-to-right as literal-then-value, which printed "%10 of a purchase".
    raise exception 'Credits may cover at most % of a purchase (PHP% here); this would apply PHP%.',
                    to_char(public.service_knob_pct(v_hive,'reward_spend_cap_pct'),'FM990') || '%',
                    to_char(v_cap,'FM999G999G990'), to_char(abs(new.amount),'FM999G999G990')
      using errcode = 'check_violation';
  end if;

  select coalesce(sum(amount),0) into v_bal from public.service_credit_ledger
   where account_type = new.account_type and account_id = new.account_id;
  if v_bal + new.amount < -0.005 then
    raise exception 'Not enough credits: balance is PHP%, this would spend PHP%.',
                    to_char(v_bal,'FM999G999G990'), to_char(abs(new.amount),'FM999G999G990')
      using errcode = 'check_violation';
  end if;
  return new;
end $function$;
