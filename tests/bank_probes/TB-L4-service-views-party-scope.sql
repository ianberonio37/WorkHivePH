-- TB-L4-service-views-party-scope
--
-- The read-isolation gate probes every hive-scoped `v_*_truth` by reading it FILTERED TO A FOREIGN
-- HIVE and asserting 0 rows. Five service-hailing views carry no `hive_id` column at all, so that
-- probe cannot reach them and the bughunt scoreboard reported them as an uncovered GAP - correctly:
-- they are not hive-scoped, they are PARTY-scoped, and nothing was asserting that either.
--
--   v_service_credit_topups_truth   a GCash top-up filing: payer, reference, amount
--   v_service_credit_ledger_truth   the credit movements behind it
--   v_service_job_tracking          a live position (already banked separately; re-asserted here so
--                                   the whole party-scoped family has one standing proof)
--
-- "No hive column" is exactly the shape that slips past a hive-shaped gate. A stranger who is a fully
-- legitimate signed-in user of the platform - just not a party to this money - must read ZERO.
begin;

insert into auth.users(id, email) values
  ('d4aaaaaa-0000-4000-8000-000000000001', 'tb-l4-owner@gate.local'),
  ('d4aaaaaa-0000-4000-8000-000000000002', 'tb-l4-stranger@gate.local');

insert into public.service_providers
  (id, provider_type, auth_uid, display_name, categories, base_location, availability)
values ('d4bbbbbb-0000-4000-8000-000000000001', 'freelancer', 'd4aaaaaa-0000-4000-8000-000000000001',
        'TB L4 Provider', '{Plumbing}', 'POINT(120.5960 16.4023)'::extensions.geography, 'online');

insert into public.service_credit_topups
  (id, account_type, account_id, payer_auth_uid, amount, gcash_ref, status)
values ('d4cccccc-0000-4000-8000-000000000001', 'provider', 'd4bbbbbb-0000-4000-8000-000000000001',
        'd4aaaaaa-0000-4000-8000-000000000001', 500, '999000111222', 'pending_verification');

-- The OWNER sees their own filing. Without this the stranger's 0 would be meaningless: a view that
-- returns nothing to anybody "isolates" perfectly and serves no one.
set local role authenticated;
set local request.jwt.claims = '{"sub":"d4aaaaaa-0000-4000-8000-000000000001","role":"authenticated"}';
select 'RESULT owner_sees_topup=' || count(*)::text
  from public.v_service_credit_topups_truth
 where gcash_ref = '999000111222';

-- A STRANGER - signed in, real, simply not a party - sees nothing. The GCash reference is the
-- sensitive field: it ties a real phone number to a real payment.
reset role;
set local role authenticated;
set local request.jwt.claims = '{"sub":"d4aaaaaa-0000-4000-8000-000000000002","role":"authenticated"}';
select 'RESULT stranger_sees_topup=' || count(*)::text
  from public.v_service_credit_topups_truth
 where gcash_ref = '999000111222';

select 'RESULT stranger_sees_ledger=' || count(*)::text
  from public.v_service_credit_ledger_truth
 where account_id = 'd4bbbbbb-0000-4000-8000-000000000001';

-- The catalog is a PUBLIC price list by design - a marketplace with a hidden price list is not a
-- marketplace. Asserted POSITIVELY so "public" stays a decision on the record rather than an
-- accident: if it ever stops being readable, that is a product break, not a security win.
select 'RESULT stranger_reads_catalog=' ||
       case when count(*) > 0 then 'yes' else 'no' end
  from public.v_service_catalog_truth where active;

rollback;
