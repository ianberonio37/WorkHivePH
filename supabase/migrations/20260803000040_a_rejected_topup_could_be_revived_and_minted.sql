-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- A REJECTED TOP-UP COULD BE REVIVED AND MINTED IN TWO STATEMENTS
--
-- Found 2026-08-03 walking the owed live-MCP scenario `LM-R-money-lifecycle-topup-rejected`, whose
-- oracle is two-part: "no credits minted, AND it cannot later be flipped to verified." The first
-- half held. The second did not.
--
-- `guard_service_topup_status` mints only on the transition pending_verification -> verified, so a
-- direct rejected -> verified flip is inert (the ledger does not move). That is what made this look
-- safe. But NOTHING constrained the transition itself, so the terminal states were not terminal:
--
--   update service_credit_topups set status='pending_verification' where id=<a REJECTED top-up>;
--   update service_credit_topups set status='verified'             where id=<the same row>;
--
-- Probed end to end as a real platform admin (role authenticated, JWT sub = the admin's uid, not
-- postgres — a superuser probe proves nothing about a guard that reads auth.uid()):
--   STEP1 rejected->pending:  SUCCEEDED
--   STEP2 pending->verified:  SUCCEEDED
--   ledger 3 -> 4, MINTED FROM A REJECTED TOP-UP: topup 777.00
--
-- ₱777 of credits for a GCash payment the platform had explicitly refused. Every credit in this
-- economy originates at this one table, and rejection is the ONLY thing standing between "a payment
-- that never arrived" and spendable money. A rejection that can be walked back by whoever issued it
-- is not a decision, it is a suggestion.
--
-- THE FIX: terminal means terminal. Once a top-up is verified or rejected, its status is frozen for
-- anyone acting as a person. The legal transitions are exactly:
--
--       pending_verification ──> verified     (mints, once, in the existing guard)
--       pending_verification ──> rejected     (mints nothing, ever)
--
-- WHAT THIS DELIBERATELY DOES NOT TOUCH, and why:
--   * the no-JWT backend path (auth.uid() is null) and the announced system-write bypass
--     (workhive.service_system_write = 'on'). Seeders and sweeps legitimately rewrite rows, and the
--     sibling intake-immutability guard three lines above scopes itself the same way. Widening the
--     scope here would break reset/seed without closing anything a person can reach.
--   * mig 38's auto-matcher, which updates `WHERE id = ... AND status = 'pending_verification'` —
--     already a legal transition, so it passes unchanged. Re-verified after this migration.
--
-- A genuine mistake (rejected the wrong receipt) is now handled the way an append-only ledger
-- handles every other mistake: the provider files the receipt again and it is verified on its own
-- merits. The reference is unique, so the original cannot be double-counted. That is one more step
-- for a rare human error, and it is the correct trade against a silent mint path.
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
  -- Found live 2026-07-30 by probing what `coalesce(old.X, new.X)` actually means on an UPDATE. The
  -- party gate below reads the STORED row, and the mint a few lines later inserts `new.account_type,
  -- new.account_id`. Those two disagreed, so ONE statement defeated the whole party check:
  --
  --   update service_credit_topups
  --      set account_id = <the admin's OWN provider>, status = 'verified'
  --    where id = <someone else's pending top-up>;
  --
  -- The gate read the OLD account, correctly saw the admin as a party to nothing, took the bypass —
  -- and the mint then credited the NEW account. Probed end to end: `credited_the_ADMIN=YES-EXPLOIT`,
  -- 500 credits. `service_credit_topups_admin_update` is `USING is_marketplace_admin()` with no WITH
  -- CHECK, so an admin may rewrite any column; nothing else stopped this.
  --
  -- The fix is to say what an admin's power over a top-up actually IS: decide it, not rewrite the
  -- receipt. The only shipped UPDATE path sets `status` alone, so nothing legitimate changes here.
  --
  -- Scoped to real callers: the no-JWT backend path and the announced system-write bypass are
  -- untouched, because seeders and sweeps legitimately rewrite rows.
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

    -- ── A DECIDED TOP-UP IS DECIDED (mig 20260803000040, this migration) ─────────────────────────
    -- The mint below fires only on pending_verification -> verified, which made a direct
    -- rejected -> verified flip inert and therefore look harmless. It was not: nothing stopped the
    -- row from being walked BACK to pending first, and the second statement then minted normally.
    -- Freezing both terminal states closes the revival without touching either legal transition.
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
  'Top-up state machine + anti-self-deal gate. pending_verification is the ONLY status a person may '
  'move from: -> verified mints exactly one topup ledger entry, -> rejected mints nothing, and both '
  'are terminal (mig 40, after a live probe revived a rejected top-up and minted PHP777 in two '
  'statements). Intake facts are immutable (mig 20260730000005). The no-JWT backend path and the '
  'announced workhive.service_system_write bypass are exempt so seeders and sweeps still work.';
