-- TB-I2-admin-bypass-only-for-non-parties.sql
--
-- WHAT THIS LOCKS. Four status-machine guards early-returned on `is_marketplace_admin()` BEFORE asking
-- whether the admin was a PARTY to the row, so an identity that is both admin and buyer/seller/provider/
-- payer could drive transitions reserved for the other side of its own deal. Fixed by mig
-- 20260730000003, which is the same one-sentence fix mig 20260729000003 applied to `guard_service_review`
-- in July: **the admin bypass applies only when the admin is NOT a party.**
--
-- The exploit identity is not hypothetical. `is_marketplace_admin()` resolves through
-- `marketplace_platform_admins.worker_name IN auth_worker_names()`, there are two platform admins today,
-- and one of them is the founder — who also sells services. Any moderator who also trades on the
-- marketplace holds it.
--
-- EVERY CELL ASSERTS BOTH HALVES, because a fix that only closes the hole may have closed moderation
-- with it. `selfdeal_*` must be BLOCKED and `moderation_*` must still WORK, in the same run, under the
-- same identity — the difference being only whose row it is.
--
-- `service_requests` is deliberately the exception and is asserted differently. Its RLS policy
-- (`service_requests_party_update`) has NO admin clause, so a non-party admin's row is filtered away
-- before any guard runs. Proven by restoring the vulnerable guard inside a rolled-back transaction:
--
--     VULNERABLE-GUARD selfdeal_own_job=1 ROWS        <-- the exploit
--     VULNERABLE-GUARD moderation_other_job=0 ROWS    <-- never worked, before OR after
--
-- So on that table the bypass had exactly ONE reachable effect: letting a party-admin skip the party
-- rules. Asserting "moderation still works" there would assert a capability the platform never had, and
-- a test that demands a behaviour nobody shipped is a test that will be "fixed" by inventing it
-- ([[feedback_gates_lock_refusal_not_permission]] cuts both ways — lock the permission that EXISTS).
--
-- Self-minted identities inside begin/rollback: nothing here depends on seeded state and nothing
-- survives. RESULT lines go to stderr via RAISE NOTICE because the reads sit inside exception blocks.
begin;

insert into auth.users(id, email) values
  ('d1dddddd-0000-4000-8000-00000000000a','tb-i2-admin@gate.local'),
  ('d1dddddd-0000-4000-8000-00000000000b','tb-i2-other@gate.local'),
  ('d1dddddd-0000-4000-8000-00000000000c','tb-i2-client@gate.local');

-- The admin: a real one, resolved the way the app resolves it (hive_members -> auth_worker_names ->
-- marketplace_platform_admins). A fake admin flag would test nothing.
insert into public.hive_members(hive_id, worker_name, role, status, auth_uid) values
  ((select id from public.hives order by id limit 1),'TB I2 Admin','worker','active',
   'd1dddddd-0000-4000-8000-00000000000a'),
  ((select id from public.hives order by id limit 1),'TB I2 Other','worker','active',
   'd1dddddd-0000-4000-8000-00000000000b');
insert into public.marketplace_platform_admins(worker_name, granted_by)
  values ('TB I2 Admin','tb-probe');

-- ---- listings: one owned by the admin, one owned by someone else ----------------------------------
insert into public.marketplace_listings(id, hive_id, seller_name, section, title, category, price, status)
values
  ('d1ffffff-0000-4000-8000-00000000000a',(select id from public.hives order by id limit 1),
   'TB I2 Admin','parts','TB I2 own listing','Tools',100,'draft'),
  ('d1ffffff-0000-4000-8000-00000000000b',(select id from public.hives order by id limit 1),
   'TB I2 Other','parts','TB I2 other listing','Tools',100,'draft');

-- ---- orders: one where the admin is the seller, one between two other people ----------------------
insert into public.marketplace_orders(id, hive_id, buyer_name, seller_name, price, status) values
  ('d1eeeeee-0000-4000-8000-00000000000a',(select id from public.hives order by id limit 1),
   'TB I2 Other','TB I2 Admin',100,'buyer_confirmed'),
  ('d1eeeeee-0000-4000-8000-00000000000b',(select id from public.hives order by id limit 1),
   'TB I2 Other','TB I2 Other',100,'buyer_confirmed');

-- ---- providers + top-ups: one the admin paid for, one paid by someone else -----------------------
insert into public.service_providers(id, provider_type, auth_uid, display_name, categories,
       base_location, availability) values
  ('d1bbbbbb-0000-4000-8000-00000000000a','freelancer','d1dddddd-0000-4000-8000-00000000000a',
   'TB I2 Admin','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'online'),
  ('d1bbbbbb-0000-4000-8000-00000000000b','freelancer','d1dddddd-0000-4000-8000-00000000000b',
   'TB I2 Other','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'online');
insert into public.service_credit_topups(id, account_type, account_id, payer_auth_uid, amount,
       gcash_ref, status) values
  ('d1aaaaab-0000-4000-8000-00000000000a','provider','d1bbbbbb-0000-4000-8000-00000000000a',
   'd1dddddd-0000-4000-8000-00000000000a',500,'900000000001','pending_verification'),
  ('d1aaaaab-0000-4000-8000-00000000000b','provider','d1bbbbbb-0000-4000-8000-00000000000b',
   'd1dddddd-0000-4000-8000-00000000000b',500,'900000000002','pending_verification');

-- ---- act as the admin ----------------------------------------------------------------------------
set local role authenticated;
set local request.jwt.claims = '{"sub":"d1dddddd-0000-4000-8000-00000000000a","role":"authenticated"}';

do $probe$
declare n int; msg text;
begin
  raise notice 'RESULT is_really_admin=%', public.is_marketplace_admin();

  -- 1. LISTINGS · "a listing goes live only after WorkHive review, not by self-publishing"
  begin
    update public.marketplace_listings set status='published'
     where id='d1ffffff-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT selfdeal_publish_own_listing=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT selfdeal_publish_own_listing=blocked'; end;
  begin
    update public.marketplace_listings set status='published'
     where id='d1ffffff-0000-4000-8000-00000000000b';
    get diagnostics n = row_count;
    raise notice 'RESULT moderation_publish_other_listing=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT moderation_publish_other_listing=BROKEN'; end;

  -- 2. ORDERS · "'released' fires the total_sales / tier bump ... neither may be self-assigned"
  begin
    update public.marketplace_orders set status='released'
     where id='d1eeeeee-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT selfdeal_release_own_order=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT selfdeal_release_own_order=blocked'; end;
  begin
    update public.marketplace_orders set status='released'
     where id='d1eeeeee-0000-4000-8000-00000000000b';
    get diagnostics n = row_count;
    raise notice 'RESULT moderation_release_other_order=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT moderation_release_other_order=BROKEN'; end;

  -- 2b/2c. THE ROW-VERSION HOLE (mig 20260730000006). Everything above asks whether an admin is a party.
  --        These ask something the party check cannot see: what if the admin CHANGES who the party is, in the
  --        same statement? The gate computes from `coalesce(OLD.seller_name, NEW.seller_name)` — the STORED
  --        row — while the consequence lands on NEW. So one statement passed the gate on the old values and
  --        collected on the new ones, and BOTH were probed live as ALLOWED before the fix:
  --
  --          orders   -> admin_total_sales=1 with the real seller left at 0 (update_seller_tier bumps
  --                      marketplace_sellers on NEW.seller_name). total_sales and tier ARE the trust signals,
  --                      so this was sales forgery.
  --          listings -> final_seller became the admin and final_status 'published': a stranger's listing,
  --                      taken over and published as the admin's own.
  --
  --        Row `...b` is used in both, because that is the one this admin is a party to in NO way — the
  --        bypass legitimately applies to them, which is exactly what made the hole reachable.
  begin
    update public.marketplace_orders set seller_name='TB I2 Admin', status='released'
     where id='d1eeeeee-0000-4000-8000-00000000000b';
    get diagnostics n = row_count;
    raise notice 'RESULT selfdeal_claim_strangers_sale=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT selfdeal_claim_strangers_sale=blocked'; end;
  begin
    update public.marketplace_listings set seller_name='TB I2 Admin', status='published'
     where id='d1ffffff-0000-4000-8000-00000000000b';
    get diagnostics n = row_count;
    raise notice 'RESULT selfdeal_takeover_strangers_listing=%',
      case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT selfdeal_takeover_strangers_listing=blocked'; end;

  -- 3. TOP-UPS · the admin branch MINTS the credit inline, so a self-verify is money creation
  begin
    update public.service_credit_topups set status='verified'
     where id='d1aaaaab-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT selfdeal_verify_own_topup=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT selfdeal_verify_own_topup=blocked'; end;
  begin
    update public.service_credit_topups set status='verified'
     where id='d1aaaaab-0000-4000-8000-00000000000b';
    get diagnostics n = row_count;
    raise notice 'RESULT moderation_verify_other_topup=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT moderation_verify_other_topup=BROKEN'; end;
end
$probe$;

-- The ledger is the money oracle, not the status column: a blocked self-verify that still minted a
-- credit would be the worst possible outcome, and the status assertion above would not have caught it
-- ([[feedback_records_that_outlive_the_action]] — check what the write LEFT BEHIND).
reset role;
do $ledger$
declare n_self int; n_other int;
begin
  select count(*) into n_self  from public.service_credit_ledger
   where ref_kind='topup' and ref_id='d1aaaaab-0000-4000-8000-00000000000a';
  select count(*) into n_other from public.service_credit_ledger
   where ref_kind='topup' and ref_id='d1aaaaab-0000-4000-8000-00000000000b';
  raise notice 'RESULT selfdeal_credit_minted=%', n_self;
  raise notice 'RESULT moderation_credit_minted=%', n_other;
end
$ledger$;

-- The TRUST oracle for the claimed-sale case. A blocked claim that nevertheless bumped the counter would be
-- the worst outcome, and the status assertion above would still read `blocked` — the same reason the top-up
-- cases read the ledger rather than the row ([[feedback_trust_signal_needs_a_living_producer]]).
do $trust$
declare n int;
begin
  select coalesce(total_sales, 0) into n from public.marketplace_sellers where worker_name='TB I2 Admin';
  raise notice 'RESULT admin_forged_sales=%', coalesce(n, 0);
end
$trust$;

rollback;
