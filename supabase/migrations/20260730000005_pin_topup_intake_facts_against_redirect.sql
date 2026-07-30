-- 20260730000005_pin_topup_intake_facts_against_redirect.sql
--
-- A platform admin could MINT PLATFORM CREDIT TO THEMSELVES in one statement.
--
-- `guard_service_topup_status` computes party-ness from the STORED row
-- (`coalesce(old.account_id, new.account_id)`) and then mints the ledger entry from the INCOMING row
-- (`new.account_type, new.account_id`). An admin who is a party to nothing therefore passes the gate on the
-- old values and is credited on the new ones:
--
--     update service_credit_topups
--        set account_id = '<the admin''s own provider>', status = 'verified'
--      where id = '<someone else''s pending top-up>';
--
-- Probed live in a rolled-back transaction before this migration was written: the write was ALLOWED, one
-- ledger row was minted, and `credited_account` was the admin's own provider — 500 credits. Two platform
-- admins exist today, so this is reachable, not theoretical.
--
-- This is the same family as mig 20260730000003 (the admin bypass applies only to a NON-party) and it slipped
-- past that fix for a subtle reason: 003 made the gate ask the right question, and this asks it about the
-- wrong ROW. A check and the action it guards must agree on which row they describe.
--
-- FIX: an admin's power over a top-up is to DECIDE it, not to rewrite it. The money-routing and receipt
-- fields become immutable for any real caller; the no-JWT backend path and the announced system-write bypass
-- are deliberately untouched so seeders and sweeps still work. The only shipped UPDATE path
-- (founder-console `svcTopupDecide`) writes `status` alone, so no working flow changes.
--
-- Everything else in this function is byte-identical to the version it replaces: the definition was
-- EXTRACTED with pg_get_functiondef and one anchored block inserted, because retyping a guard from a partial
-- read is exactly how three unrelated security rules were once silently dropped from its sibling.

CREATE OR REPLACE FUNCTION public.guard_service_topup_status()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
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

  -- ── THE INTAKE FACTS ARE IMMUTABLE (mig 20260730000005) ────────────────────────────────────────────
  -- Found live 2026-07-30 by probing what `coalesce(old.X, new.X)` actually means on an UPDATE. The party
  -- gate below reads the STORED row, and the mint a few lines later inserts `new.account_type,
  -- new.account_id`. Those two disagreed, so ONE statement defeated the whole party check:
  --
  --   update service_credit_topups
  --      set account_id = <the admin's OWN provider>, status = 'verified'
  --    where id = <someone else's pending top-up>;
  --
  -- The gate read the OLD account, correctly saw the admin as a party to nothing, took the bypass — and the
  -- mint then credited the NEW account. Probed end to end: `credited_the_ADMIN=YES-EXPLOIT`, 500 credits.
  -- `service_credit_topups_admin_update` is `USING is_marketplace_admin()` with no WITH CHECK, so an admin
  -- may rewrite any column; nothing else stopped this.
  --
  -- The fix is to say what an admin's power over a top-up actually IS: decide it, not rewrite the receipt.
  -- The only shipped UPDATE path (founder-console `svcTopupDecide`) sets `status` alone, so nothing legitimate
  -- changes here. Verification/rejection still works; laundering the destination does not.
  --
  -- Scoped to real callers: the no-JWT backend path and the announced system-write bypass are untouched,
  -- because seeders and sweeps legitimately rewrite rows.
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
