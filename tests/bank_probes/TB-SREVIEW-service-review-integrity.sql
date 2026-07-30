-- TB-SREVIEW-service-review-integrity.sql
--
-- `guard_service_review` protects the integrity of a SERVICE review (request_id IS NOT NULL — classic listing
-- reviews follow other rules). A review is the social proof buyers price a provider against, so the guard:
--   * pins verified_purchase := true and reviewer_auth_uid := auth.uid() on every branch (no forged provenance)
--   * refuses a review until the job is completed/settled (no reviewing a job that never happened)
--   * refuses a review whose DIRECTION does not match the reviewer's SIDE (only the client reviews the
--     provider; only the matched provider reviews the client)
--   * keeps the admin bypass ONLY for an admin who is NOT a party — the one trust guard that already applies
--     the mig-003 self-deal rule ([[feedback_admin_bypass_before_party_check_is_selfdeal]]), so an admin
--     reviewing their OWN job does not get the moderator pass.
--
-- Found unscored 2026-07-31 (ARC 13 / F). The guard is CORRECT — it was simply unwatched, so deleting the
-- status gate, a direction check or a pin would have gone unnoticed.
--
-- Guard-isolated: fixtures are planted as postgres (auth.uid() null -> vetted backend path, which also lets the
-- request be BORN 'settled'/'in_progress' past guard_service_request_status), then each reviewer acts with its
-- jwt claims set but RLS bypassed, so whatever refuses is THIS trigger. Every refusal is paired with the
-- legitimate review, so "protects review integrity" is separated from "rejects reviews".
begin;

insert into auth.users(id, email) values
  ('ce000000-0000-4000-8000-00000000000a','tb-srev-client@gate.local'),
  ('ce000000-0000-4000-8000-00000000000b','tb-srev-provider@gate.local'),
  ('ce000000-0000-4000-8000-00000000000c','tb-srev-stranger@gate.local');

insert into public.service_providers(id, provider_type, display_name, auth_uid) values
  ('ce000000-0000-4000-8000-0000000000f1','freelancer','TB SRev Provider','ce000000-0000-4000-8000-00000000000b');

-- an ADMIN who is also a party (the client) to their OWN settled job — the mig-003 self-deal case
insert into auth.users(id, email) values ('ce000000-0000-4000-8000-00000000000d','tb-srev-admin@gate.local');
insert into public.marketplace_sellers(id, worker_name, auth_uid, tier, kyb_verified, cert_verified, total_sales, rating_count)
  values ('ce000000-0000-4000-8000-0000000000f2','TB SRev Admin','ce000000-0000-4000-8000-00000000000d','bronze',false,false,0,0);
insert into public.marketplace_platform_admins(worker_name, granted_by) values ('TB SRev Admin','tb-fixture');

insert into public.service_requests(id, client_auth_uid, matched_provider_id, status, mode, custom_scope) values
  ('ce000000-0000-4000-8000-0000000000d1','ce000000-0000-4000-8000-00000000000a',
   'ce000000-0000-4000-8000-0000000000f1','settled','instant','TB probe scope'),
  ('ce000000-0000-4000-8000-0000000000d2','ce000000-0000-4000-8000-00000000000a',
   'ce000000-0000-4000-8000-0000000000f1','in_progress','instant','TB probe scope'),
  -- the admin's OWN settled job (admin is the client)
  ('ce000000-0000-4000-8000-0000000000d3','ce000000-0000-4000-8000-00000000000d',
   'ce000000-0000-4000-8000-0000000000f1','settled','instant','TB probe scope');

-- ── CLIENT (a party) reviews the provider on a SETTLED job — the legitimate case ──
select set_config('request.jwt.claims',
  '{"sub":"ce000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);
do $probe$
declare n int; v_verified boolean; v_reviewer uuid;
begin
  begin
    insert into public.marketplace_reviews(id, request_id, reviewer_name, rating, direction)
      values ('ce000000-0000-4000-8000-00000000aa01','ce000000-0000-4000-8000-0000000000d1','TB Client',5,'client_to_provider');
    get diagnostics n=row_count; raise notice 'RESULT client_reviews_provider=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT client_reviews_provider=BLOCKED sqlstate=%', sqlstate; end;

  -- the guard pins these server-side regardless of what the client sent
  select verified_purchase, reviewer_auth_uid into v_verified, v_reviewer
    from public.marketplace_reviews where id='ce000000-0000-4000-8000-00000000aa01';
  raise notice 'RESULT verified_pinned=%', coalesce(v_verified::text,'null');
  raise notice 'RESULT reviewer_pinned=%', case when v_reviewer='ce000000-0000-4000-8000-00000000000a' then 'self' else coalesce(v_reviewer::text,'null') end;

  -- wrong DIRECTION: the client is not the provider, so provider_to_client is refused
  begin
    insert into public.marketplace_reviews(id, request_id, reviewer_name, rating, direction)
      values ('ce000000-0000-4000-8000-00000000aa02','ce000000-0000-4000-8000-0000000000d1','TB Client',5,'provider_to_client');
    get diagnostics n=row_count; raise notice 'RESULT client_wrong_direction=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT client_wrong_direction=blocked'; end;

  -- the job is not finished: a review on an in_progress request is refused
  begin
    insert into public.marketplace_reviews(id, request_id, reviewer_name, rating, direction)
      values ('ce000000-0000-4000-8000-00000000aa03','ce000000-0000-4000-8000-0000000000d2','TB Client',5,'client_to_provider');
    get diagnostics n=row_count; raise notice 'RESULT review_open_job=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT review_open_job=blocked'; end;

  -- a review pointing at a request that does not exist is refused (the guard's first gate). Pins the
  -- 'unknown service request' raise so refusal_removed on it cannot pass silently.
  begin
    insert into public.marketplace_reviews(id, request_id, reviewer_name, rating, direction)
      values ('ce000000-0000-4000-8000-00000000aa06','ce000000-0000-4000-8000-00000000dead','TB Client',5,'client_to_provider');
    get diagnostics n=row_count; raise notice 'RESULT unknown_request=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT unknown_request=blocked'; end;
end $probe$;

-- ── PROVIDER (the other party) reviews the client — also legitimate ──
select set_config('request.jwt.claims',
  '{"sub":"ce000000-0000-4000-8000-00000000000b","role":"authenticated"}', true);
do $probe$
declare n int;
begin
  begin
    insert into public.marketplace_reviews(id, request_id, reviewer_name, rating, direction)
      values ('ce000000-0000-4000-8000-00000000aa04','ce000000-0000-4000-8000-0000000000d1','TB Provider',4,'provider_to_client');
    get diagnostics n=row_count; raise notice 'RESULT provider_reviews_client=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT provider_reviews_client=BLOCKED sqlstate=%', sqlstate; end;
end $probe$;

-- ── ADMIN who is a PARTY to their own job does NOT get the moderator bypass (the mig-003 self-deal rule) ──
select set_config('request.jwt.claims',
  '{"sub":"ce000000-0000-4000-8000-00000000000d","role":"authenticated"}', true);
do $probe$
declare n int;
begin
  raise notice 'RESULT admin_party_is_admin=%', public.is_marketplace_admin();
  -- the admin is the CLIENT of d3; posting provider_to_client (a direction only the provider may use) must be
  -- REFUSED, because a party-admin does not get the bypass. If the bypass applied to a party, this would pass.
  begin
    insert into public.marketplace_reviews(id, request_id, reviewer_name, rating, direction)
      values ('ce000000-0000-4000-8000-00000000aa07','ce000000-0000-4000-8000-0000000000d3','TB SRev Admin',5,'provider_to_client');
    get diagnostics n=row_count; raise notice 'RESULT admin_party_wrong_direction=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT admin_party_wrong_direction=blocked'; end;
  -- as the client-party they CAN post the correct direction (client_to_provider) on their own settled job
  begin
    insert into public.marketplace_reviews(id, request_id, reviewer_name, rating, direction)
      values ('ce000000-0000-4000-8000-00000000aa08','ce000000-0000-4000-8000-0000000000d3','TB SRev Admin',5,'client_to_provider');
    get diagnostics n=row_count; raise notice 'RESULT admin_party_right_direction=%', case when n>0 then 'allowed' else 'BLOCKED' end;
  exception when others then raise notice 'RESULT admin_party_right_direction=BLOCKED'; end;
end $probe$;

-- ── STRANGER (no party) cannot review at all ──
select set_config('request.jwt.claims',
  '{"sub":"ce000000-0000-4000-8000-00000000000c","role":"authenticated"}', true);
do $probe$
declare n int;
begin
  begin
    insert into public.marketplace_reviews(id, request_id, reviewer_name, rating, direction)
      values ('ce000000-0000-4000-8000-00000000aa05','ce000000-0000-4000-8000-0000000000d1','TB Stranger',5,'client_to_provider');
    get diagnostics n=row_count; raise notice 'RESULT stranger_reviews=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT stranger_reviews=blocked'; end;
end $probe$;

rollback;
