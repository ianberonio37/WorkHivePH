-- My non-transferable guard refused every cashback, so settling a job stopped working.
--
-- The guard carried two rules. The first is the real one: nobody may write credits into ANOTHER person's
-- wallet, which is what denies credits a resale market. The second said "a client may never mint a
-- positive balance by hand" and refused any positive entry that was not a reward_earn.
--
-- That second rule caught `mint_service_cashback`, which is a positive consumer entry written by a
-- trigger during settlement. SECURITY DEFINER changes the executing role but not the JWT, so the write
-- looked exactly like the client writing to themselves. Result: completed -> settled was refused, and
-- the whole money spine stopped at the last step. Found by the arc and aftermath specs, not by reasoning.
--
-- AND THE RULE WAS NEVER NEEDED. Checked rather than assumed: `authenticated` holds NO INSERT privilege
-- on service_credit_ledger, and the only policy on the table is a SELECT. A client cannot write a ledger
-- row at all, by any path. The rule defended against something already impossible while breaking
-- something real -- the worst trade a guard can make.
--
-- This is the third time in this arc that a new guard silently broke an existing path (reward_fund vs
-- the exclusivity rule; the transfer guard vs the reward legs; this). The pattern is the same each time:
-- a guard reasons about WHO is writing, while the legitimate writers are triggers running under the
-- caller's JWT. The lesson worth keeping is that a new ledger guard must be run against the EXISTING
-- mint paths -- commission, cashback, adjustment, top-up -- before it is trusted, because every one of
-- them writes on someone's behalf.

create or replace function public.guard_credits_non_transferable()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
begin
  -- Vetted platform acts: seeders, sweeps, and the listing-reward path, which announces itself.
  if auth.uid() is null or current_setting('workhive.service_system_write', true) = 'on' then
    return new;
  end if;

  -- THE non-transferability guarantee, and the only rule this guard needs: credits never move into a
  -- wallet that is not the caller's. Platform mints to the caller's own wallet (cashback, starter grant)
  -- pass; a gift to a friend does not. No resale market means no realizable gain, which is the factor the
  -- SEC investment-contract framework weights most heavily.
  if new.account_type = 'consumer' and new.account_id is distinct from auth.uid() then
    raise exception 'Credits cannot be moved between people. They are earned on a purchase and spent on '
                    'a purchase; there is no transfer, and that is deliberate - a credit that can be '
                    'passed around is a credit with a resale market.'
      using errcode = '42501';
  end if;
  return new;
end $function$;

comment on function public.guard_credits_non_transferable() is
  'Refuses credit movements into a wallet that is not the caller''s. Deliberately does NOT police the '
  'SIGN of an entry: a positive-amount rule here refused mint_service_cashback (a trigger write under '
  'the client''s own JWT) and broke settlement, while defending against a client INSERT that RLS and '
  'table privileges already make impossible.';
