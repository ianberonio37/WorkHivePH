-- TB-MINT-topup-party-routes-and-mint-once.sql
--
-- THE MONEY GUARD HAD THREE UNTESTED RULES, and a fourth wave of mutation operators found all three at once.
-- `guard_service_topup_status` is the only guard on this platform that CREATES money: verifying a top-up
-- inserts the `service_credit_ledger` row inline. Its four existing cells covered the payer route and nothing
-- else, so these survived:
--
--     SURVIVED mint_on_any_prior_status              re-verifying an already-verified top-up mints AGAIN
--     SURVIVED party_provider_account_branch_removed verifying another's top-up INTO AN ACCOUNT YOU OWN
--     SURVIVED party_consumer_account_branch_removed the same, for a consumer wallet
--
-- The shipped guard is CORRECT on all three — these are test gaps, not defects. That distinction is the point:
-- a mutation survivor says "nothing would notice if this rule were deleted", which is a statement about the
-- bank, and the fix is a cell, not a migration.
--
-- WHY THE PARTY ROUTES MATTER. `v_is_party` on this guard is a three-branch disjunction, and the guard's own
-- comment says why: "verifying a top-up you filed is self-minting, and so is verifying someone else's top-up
-- into your own provider account." Only the first branch had a cell. Authority derived through a disjunction
-- gives every branch its own independent authorisation path, and an untested branch is unmonitored code —
-- an admin who owns the destination account is just as much a party as the one who filed the receipt, and
-- both mint real credit into an account they control.
--
-- WHY MINT-ONCE MATTERS. The mint is gated on `TG_OP = 'UPDATE' AND new.status = 'verified' AND old.status =
-- 'pending_verification'`. Only that last conjunct makes it once-only: drop it and every subsequent UPDATE
-- that leaves the row `verified` mints the amount again, so an admin re-saving a verified top-up doubles it.
-- The status column looks identical in both worlds — **only the ledger can tell them apart**, which is why
-- every assertion here counts ledger ROWS rather than reading a status
-- ([[feedback_records_that_outlive_the_action]]).
--
-- The admin here is a party via the ACCOUNT, never the payer: someone else always files the top-up. That
-- isolates the branch under test, since a payer-route party would be refused by the branch TB-I2 already
-- covers and the cell would pass without exercising anything new.
begin;

insert into auth.users(id, email) values
  ('e1111111-0000-4000-8000-00000000000a','tb-mint-admin@gate.local'),
  ('e1111111-0000-4000-8000-00000000000b','tb-mint-payer@gate.local'),
  ('e1111111-0000-4000-8000-00000000000c','tb-mint-other@gate.local');

insert into public.hive_members(hive_id, worker_name, role, status, auth_uid) values
  ((select id from public.hives order by id limit 1),'TB Mint Admin','worker','active',
   'e1111111-0000-4000-8000-00000000000a');
insert into public.marketplace_platform_admins(worker_name, granted_by)
  values ('TB Mint Admin','tb-probe');

-- Two provider profiles: one the ADMIN owns (the destination that makes them a party) and one owned by an
-- unrelated account (the control, where the admin is a party to nothing and moderation must still work).
insert into public.service_providers(id, provider_type, auth_uid, display_name, categories,
       base_location, availability) values
  ('e2222222-0000-4000-8000-00000000000a','freelancer','e1111111-0000-4000-8000-00000000000a',
   'TB Mint Admin Co','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'online'),
  ('e2222222-0000-4000-8000-00000000000b','freelancer','e1111111-0000-4000-8000-00000000000c',
   'TB Mint Other Co','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'online');

-- Every top-up is FILED BY THE PAYER, never by the admin.
insert into public.service_credit_topups(id, account_type, account_id, payer_auth_uid, amount,
       gcash_ref, status) values
  -- destination = the provider account the ADMIN owns
  ('e3333333-0000-4000-8000-00000000000a','provider','e2222222-0000-4000-8000-00000000000a',
   'e1111111-0000-4000-8000-00000000000b',500,'920000000001','pending_verification'),
  -- destination = the ADMIN's own consumer wallet
  ('e3333333-0000-4000-8000-00000000000b','consumer','e1111111-0000-4000-8000-00000000000a',
   'e1111111-0000-4000-8000-00000000000b',500,'920000000002','pending_verification'),
  -- destination = an unrelated provider: the admin is a party to NOTHING here
  ('e3333333-0000-4000-8000-00000000000c','provider','e2222222-0000-4000-8000-00000000000b',
   'e1111111-0000-4000-8000-00000000000b',500,'920000000003','pending_verification'),
  -- the row used for the mint-once case, verified below through the SYSTEM path so it carries a real ledger
  -- row before the admin ever touches it
  ('e3333333-0000-4000-8000-00000000000d','provider','e2222222-0000-4000-8000-00000000000b',
   'e1111111-0000-4000-8000-00000000000b',500,'920000000004','pending_verification');

-- Verified as postgres (auth.uid() is null -> the vetted backend path), which is the ONLY way to arrive at a
-- verified row with its ledger entry already minted. Inserting `verified` directly would not mint, because
-- the mint is gated on TG_OP = 'UPDATE' — so the fixture would not represent a real verified top-up.
update public.service_credit_topups set status='verified'
 where id='e3333333-0000-4000-8000-00000000000d';

do $baseline$
declare n int;
begin
  select count(*) into n from public.service_credit_ledger
   where ref_kind='topup' and ref_id='e3333333-0000-4000-8000-00000000000d';
  -- Non-vacuity: if the system path did not mint, the mint-once assertion below would be comparing 0 to 0
  -- and would hold no matter what the guard did.
  raise notice 'RESULT system_verify_minted_once=%', n;
end
$baseline$;

set local role authenticated;
set local request.jwt.claims = '{"sub":"e1111111-0000-4000-8000-00000000000a","role":"authenticated"}';

do $probe$
declare n int;
begin
  raise notice 'RESULT mint_admin_is_admin=%', public.is_marketplace_admin();

  -- 1. PARTY VIA A PROVIDER ACCOUNT THE ADMIN OWNS. Not the payer — the destination.
  begin
    update public.service_credit_topups set status='verified'
     where id='e3333333-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT selfdeal_verify_into_own_provider=%',
      case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then
    raise notice 'RESULT selfdeal_verify_into_own_provider=blocked'; end;

  -- 2. PARTY VIA THE ADMIN'S OWN CONSUMER WALLET.
  begin
    update public.service_credit_topups set status='verified'
     where id='e3333333-0000-4000-8000-00000000000b';
    get diagnostics n = row_count;
    raise notice 'RESULT selfdeal_verify_into_own_wallet=%',
      case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then
    raise notice 'RESULT selfdeal_verify_into_own_wallet=blocked'; end;

  -- 3. THE MODERATION HALF. Same admin, a top-up they are a party to in no way: verifying it must still
  --    work, or a "fix" that closed the two holes above by refusing everything would look identical.
  begin
    update public.service_credit_topups set status='verified'
     where id='e3333333-0000-4000-8000-00000000000c';
    get diagnostics n = row_count;
    raise notice 'RESULT moderation_verify_unrelated=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT moderation_verify_unrelated=BROKEN'; end;

  -- 4. MINT ONCE. Re-saving an already-verified top-up. The status is `verified` before and after, so the
  --    row itself proves nothing — the ledger count below is the whole assertion.
  begin
    update public.service_credit_topups set status='verified'
     where id='e3333333-0000-4000-8000-00000000000d';
    get diagnostics n = row_count;
    raise notice 'RESULT reverify_write_accepted=%', case when n>0 then 'yes' else 'no' end;
  exception when others then raise notice 'RESULT reverify_write_accepted=refused'; end;
end
$probe$;

reset role;
select set_config('request.jwt.claims', '', true);

do $ledger$
declare n_own int; n_wallet int; n_unrelated int; n_reverify int;
begin
  select count(*) into n_own       from public.service_credit_ledger
   where ref_kind='topup' and ref_id='e3333333-0000-4000-8000-00000000000a';
  select count(*) into n_wallet    from public.service_credit_ledger
   where ref_kind='topup' and ref_id='e3333333-0000-4000-8000-00000000000b';
  select count(*) into n_unrelated from public.service_credit_ledger
   where ref_kind='topup' and ref_id='e3333333-0000-4000-8000-00000000000c';
  select count(*) into n_reverify  from public.service_credit_ledger
   where ref_kind='topup' and ref_id='e3333333-0000-4000-8000-00000000000d';
  -- The money oracle for all four cases. A blocked self-verify that still minted would be the worst
  -- outcome of the lot, and every status assertion above would still read `blocked`.
  raise notice 'RESULT credit_minted_own_provider=%', n_own;
  raise notice 'RESULT credit_minted_own_wallet=%', n_wallet;
  raise notice 'RESULT credit_minted_unrelated=%', n_unrelated;
  raise notice 'RESULT credit_after_reverify=%', n_reverify;
end
$ledger$;

rollback;
