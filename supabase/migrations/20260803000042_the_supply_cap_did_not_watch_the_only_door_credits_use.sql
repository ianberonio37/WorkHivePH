-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- THE 10,000,000 SUPPLY CAP DID NOT WATCH THE ONLY DOOR CREDITS ACTUALLY USE
--
-- Ian's model, in his words: "buy credits first from workhive, where the 10,000,000 credits will be
-- deducted and those bought credits will be added to the total credits in circulation."
--
-- The deduction was not happening. Found 2026-08-03 walking the owed live-MCP scenario
-- `LM-R-money-lifecycle-supply-cap`.
--
-- `issue_credits(amount)` is the ceiling: it takes `authorised_credits - issued_credits FOR UPDATE`,
-- refuses when the remainder is too small, and increments `issued_credits`. Exactly one function
-- called it — `claim_starter_grant`, correctly, with the comment "a grant is not minted outside the
-- ceiling". The OTHER mint, the one in `guard_service_topup_status` that fires on every verified
-- GCash top-up, inserted its ledger row directly and never touched the treasury.
--
-- MEASURED, on live data:
--
--   credit_treasury   authorised = 10,000,000.00   issued = 0.00
--   ledger            topup      =      1,500.00   (2 rows)  starter_grant = 0.00 (0 rows)
--
-- Every credit that exists came through the door nobody was counting. Two consequences, and the
-- second is worse than the first:
--
--   1. THE CAP WAS UNENFORCED on the primary mint path. `issued_credits` never grows, so
--      `authorised - issued` is always the full 10,000,000 and no top-up could ever be refused for
--      exhausting the supply. The ceiling that "guarantees every credit in circulation is
--      honourable" was guarding a door credits do not use.
--
--   2. THE NUMBER ON THE SCREEN WAS FALSE. founder-console reads authorised_credits and
--      issued_credits from v_credit_posture to state the platform's own position. It showed 0
--      issued while PHP1,500 circulated. A money figure that is confidently wrong is worse than one
--      that is missing — this platform has banked that lesson twice already (the deleted "Earned
--      revenue" tile, the wallet that read PHP0 to someone holding PHP340).
--
-- THE FIX, in two parts:
--
--   * the top-up mint now issues against the ceiling, exactly as the starter grant does. Because
--     `issue_credits` raises check_violation with a person-shaped sentence, a verification that
--     would breach the cap is refused and the founder READS why — platform-actions already surfaces
--     23514/P0001 verbatim through refusalMessage().
--
--   * `issued_credits` is back-filled to what was actually minted, so the counter stops lying about
--     history. This is a COUNTER, not the ledger: the ledger is append-only and untouched, and
--     correcting a counter to match the rows it summarises is not rewriting history, it is ending a
--     disagreement with it. The backfill is computed from the ledger rather than hardcoded, so it is
--     correct whenever this migration runs.
--
-- ORDERING NOTE: issue_credits is called BEFORE the ledger insert. If the cap refuses, the whole
-- statement aborts and no credit row is written — the refusal and the mint cannot disagree.
-- ═══════════════════════════════════════════════════════════════════════════════════════════════

create or replace function public.guard_service_topup_status()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare
  v_is_party boolean;
begin
  -- A party to a top-up is the person who says they paid, OR the account the credit lands in. Both
  -- matter: verifying a top-up you filed is self-minting, and so is verifying someone else's top-up
  -- into your own provider account.
  v_is_party := (coalesce(old.payer_auth_uid, new.payer_auth_uid) = auth.uid())
             or (coalesce(old.account_type, new.account_type) = 'provider'
                 and coalesce(old.account_id, new.account_id)
                     in (select id from public.service_providers where auth_uid = auth.uid()))
             or (coalesce(old.account_type, new.account_type) = 'consumer'
                 and coalesce(old.account_id, new.account_id) = auth.uid());

  -- ── THE INTAKE FACTS ARE IMMUTABLE (mig 20260730000005) ────────────────────────────────────────
  -- The party gate reads the STORED row while the mint inserts the NEW one, so one statement that
  -- rewrote account_id while setting status='verified' defeated the whole check and credited the
  -- admin's own provider. An admin decides a top-up; they do not rewrite the receipt.
  if TG_OP = 'UPDATE' and auth.uid() is not null
     and coalesce(current_setting('workhive.service_system_write', true), '') <> 'on' then
    if new.account_type   is distinct from old.account_type
       or new.account_id  is distinct from old.account_id
       or new.payer_auth_uid is distinct from old.payer_auth_uid
       or new.amount      is distinct from old.amount
       or new.gcash_ref   is distinct from old.gcash_ref then
      raise exception 'Not allowed: a top-up''s intake facts (account, payer, amount, reference) are immutable - a verification decides a top-up, it does not rewrite it'
        using errcode = 'check_violation';
    end if;

    -- ── A DECIDED TOP-UP IS DECIDED (mig 20260803000040) ────────────────────────────────────────
    -- The mint fires only on pending_verification -> verified, which made a direct rejected ->
    -- verified flip inert and therefore look harmless. Nothing stopped the row being walked BACK to
    -- pending first, and the second statement then minted normally: PHP777 from a refused payment.
    if old.status in ('verified', 'rejected')
       and new.status is distinct from old.status then
      raise exception 'Not allowed: this top-up was already % - a decided top-up cannot be re-opened. If it was decided in error, the provider files the receipt again and it is verified on its own merits.', old.status
        using errcode = 'check_violation';
    end if;
  end if;

  if auth.uid() is null
     or (public.is_marketplace_admin() and not v_is_party)
     or current_setting('workhive.service_system_write', true) = 'on' then
    -- a verification mints the ledger entry exactly once
    if TG_OP = 'UPDATE' and new.status = 'verified' and old.status = 'pending_verification' then
      new.verified_by := coalesce(new.verified_by, auth.uid());
      new.verified_at := coalesce(new.verified_at, now());

      -- ── ISSUE AGAINST THE CEILING (mig 20260803000042) ───────────────────────────────────────
      -- This was the missing half of the supply cap. claim_starter_grant issued against it; this
      -- mint — the only one that has ever actually produced credits — did not, so issued_credits sat
      -- at 0 while PHP1,500 circulated and no top-up could ever be refused for exhausting supply.
      -- BEFORE the insert on purpose: if the cap refuses, the statement aborts and no credit row is
      -- written, so the refusal and the mint can never disagree.
      perform public.issue_credits(new.amount);

      insert into public.service_credit_ledger (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
      values (new.account_type, new.account_id, 'topup', new.amount, 'topup', new.id, 'GCash ref ' || new.gcash_ref);
    end if;
    return new;
  end if;
  -- raw client: may only file a PENDING intake row for themself
  if TG_OP = 'INSERT' then
    if new.status <> 'pending_verification' then
      raise exception 'Not allowed: a top-up starts pending_verification (the founder verifies it)' using errcode = 'check_violation';
    end if;
    if new.payer_auth_uid is distinct from auth.uid() then
      raise exception 'Not allowed: payer_auth_uid must be the caller' using errcode = 'check_violation';
    end if;
    return new;
  end if;
  raise exception 'Not allowed: top-up verification is founder/admin-only, and never on a top-up you are a party to' using errcode = 'check_violation';
end
$function$;

comment on function public.guard_service_topup_status() is
  'Top-up state machine, anti-self-deal gate, and the issuance point for every credit that enters '
  'circulation. pending_verification is the ONLY status a person may move from: -> verified issues '
  'against the 10,000,000 ceiling (mig 42) then mints exactly one topup ledger entry, -> rejected '
  'mints nothing, and both are terminal (mig 40). Intake facts are immutable (mig 20260730000005). '
  'The no-JWT backend path and workhive.service_system_write bypass the party gate so seeders and '
  'sweeps work — they still issue against the cap.';

-- ── Back-fill the counter to match the rows it summarises ──────────────────────────────────────
-- Not a history rewrite: the ledger is append-only and untouched. This ends a disagreement between
-- a counter and the rows it was always meant to count. Computed from the ledger, never hardcoded,
-- and clamped so a re-run cannot double-count.
do $$
declare v_minted numeric; v_before numeric;
begin
  select coalesce(sum(amount), 0) into v_minted
    from public.service_credit_ledger
   where entry_type in ('topup', 'starter_grant');

  select issued_credits into v_before from public.credit_treasury where id = 1 for update;

  if v_minted > v_before then
    update public.credit_treasury
       set issued_credits = v_minted, updated_at = now()
     where id = 1;
    raise notice 'mig 42 backfill: issued_credits % -> % (matching % of minted ledger rows)',
                 v_before, v_minted, v_minted;
  else
    raise notice 'mig 42 backfill: issued_credits already >= minted (% >= %), left alone',
                 v_before, v_minted;
  end if;
end $$;

-- Prove the two numbers now agree, and fail loudly if they do not. A migration that reports success
-- while leaving a money counter wrong is the exact "green while broken" shape this platform keeps
-- getting bitten by.
do $$
declare v_minted numeric; v_issued numeric;
begin
  select coalesce(sum(amount), 0) into v_minted from public.service_credit_ledger
   where entry_type in ('topup', 'starter_grant');
  select issued_credits into v_issued from public.credit_treasury where id = 1;
  if v_issued < v_minted - 0.005 then
    raise exception 'mig 42 FAILED: treasury issued % is still below the % actually minted', v_issued, v_minted;
  end if;
end $$;
