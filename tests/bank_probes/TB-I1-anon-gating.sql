-- TB-I1-anon-gating
--
-- UFAI I1 (auth gating), recorded `pct: null` on marketplace.html — and a hole in the BANK's own SQL
-- lane. The derived matrix generates an `anon` authority-negative for every guarded transition, but
-- the runner maps `anon` to no probe identity and skips every one of them. So the partition with the
-- largest possible blast radius — an unauthenticated stranger on the public internet — was enumerated
-- as an obligation and never executed. This cell executes it.
--
-- A marketplace has to be OPEN and CLOSED at the same time, and both halves are asserted here:
--   OPEN   a stranger who has not signed up must be able to browse the CATALOGUE, or there is no
--          marketplace to join
--   CLOSED that same stranger must not create a job, read a live position, or see anyone's money
--
-- The provider DIRECTORY sits between the two and is recorded as OBSERVED rather than asserted: anon
-- is refused today, which is correct for the current product (its only page read is inside
-- svcShowQuotes, where the caller is a signed-in client) - and worth knowing if that directory is ever
-- meant to become an SEO surface the way the classic seller profiles are.
--
-- Run as the `anon` role with NO jwt claims, which is exactly what an unauthenticated page has.
begin;

-- Planted with the service role first, so the anon reads below are looking for something that really
-- exists. Asserting "anon sees 0" against an empty table proves nothing at all.
insert into auth.users(id, email) values
  ('d7aaaaaa-0000-4000-8000-000000000001', 'tb-i1-client@gate.local'),
  ('d7aaaaaa-0000-4000-8000-000000000002', 'tb-i1-provider@gate.local');

insert into public.service_providers
  (id, provider_type, auth_uid, display_name, categories, base_location, availability, live_location)
values ('d7bbbbbb-0000-4000-8000-000000000001', 'freelancer', 'd7aaaaaa-0000-4000-8000-000000000002',
        'TB I1 Provider', '{Plumbing}', 'POINT(120.5960 16.4023)'::extensions.geography, 'on_job',
        'POINT(120.6000 16.4100)'::extensions.geography);

insert into public.service_requests
  (id, client_auth_uid, mode, custom_scope, location, status, matched_provider_id)
values ('d7cccccc-0000-4000-8000-000000000001', 'd7aaaaaa-0000-4000-8000-000000000001', 'instant',
        'tb i1 probe', 'POINT(120.5960 16.4023)'::extensions.geography, 'en_route',
        'd7bbbbbb-0000-4000-8000-000000000001');

insert into public.service_credit_topups
  (account_type, account_id, payer_auth_uid, amount, gcash_ref, status)
values ('provider', 'd7bbbbbb-0000-4000-8000-000000000001', 'd7aaaaaa-0000-4000-8000-000000000002',
        500, '888000111222', 'pending_verification');

-- ── the unauthenticated stranger ────────────────────────────────────────────────────────────────
-- Every read runs inside its own exception block. A single 42501 aborts a transaction in postgres, so
-- an unguarded sequence stops at the first denial and the remaining assertions silently never run -
-- which is how a probe reports one line and looks finished.
set local role anon;

do $$
declare n int; v text;
begin
  -- OPEN: the rate card. A marketplace nobody can price has nobody to join it.
  begin
    select count(*) into n from public.v_service_catalog_truth where active;
    v := case when n > 0 then 'yes' else 'no' end;
  exception when others then v := 'denied'; end;
  raise notice 'RESULT anon_reads_catalog=%', v;

  -- The SERVICE provider directory. Recorded as OBSERVED contract, not as a wish: the only page read
  -- of v_service_provider_truth is inside svcShowQuotes, where the caller is a signed-in client
  -- looking at quotes on their own request. anon holds no SELECT on the service_providers base table
  -- and the view is security_invoker, so anon is refused - correct for today's product, and worth
  -- knowing if the directory is ever meant to be an SEO surface like the classic seller profiles.
  begin
    select count(*) into n from public.v_service_provider_truth;
    v := case when n > 0 then 'readable' else 'empty' end;
  exception when others then v := 'denied'; end;
  raise notice 'RESULT anon_reads_directory=%', v;

  -- CLOSED: a live position. This is the column with a person attached to it.
  begin
    select count(*) into n from public.v_service_job_tracking
     where request_id = 'd7cccccc-0000-4000-8000-000000000001';
    v := n::text;
  exception when others then v := '0'; end;   -- a denial IS zero rows seen
  raise notice 'RESULT anon_reads_tracking=%', v;

  -- CLOSED: someone else's money, including the GCash reference.
  begin
    select count(*) into n from public.v_service_credit_topups_truth where gcash_ref = '888000111222';
    v := n::text;
  exception when others then v := '0'; end;
  raise notice 'RESULT anon_reads_topups=%', v;

  -- CLOSED: an existing job. An anon who can read the hail feed can harvest addresses.
  begin
    select count(*) into n from public.service_requests
     where id = 'd7cccccc-0000-4000-8000-000000000001';
    v := n::text;
  exception when others then v := '0'; end;
  raise notice 'RESULT anon_reads_requests=%', v;

  -- CLOSED: creating work at all.
  begin
    insert into public.service_requests (client_auth_uid, mode, custom_scope, location, status)
    values ('d7aaaaaa-0000-4000-8000-000000000001', 'instant', 'tb i1 anon write',
            'POINT(120.5960 16.4023)'::extensions.geography, 'requested');
    v := '1';
  exception when others then v := '0'; end;
  raise notice 'RESULT anon_can_create_job=%', v;
end $$;

rollback;
