-- TB-TRUST-provider-cannot-self-verify.sql
--
-- `guard_service_provider_writes` is the third of the four guards no registered gate names (§12.1), and it is
-- the one that protects TRUST. Two columns, four rules, and both columns are things a provider must not be able
-- to say about themselves:
--
--   `verified`     the marketplace's trust badge. Self-declared, it is worthless — and worse than worthless,
--                  because buyers price against it.
--   `availability` `on_job` is DISPATCH state, set by the job lifecycle. A provider who can set it themselves
--                  can appear busy to dodge the matcher, or appear free while already working.
--
-- Four rules, because each column is protected on BOTH branches and a guard that covers only one is a guard
-- with a hole:
--
--   INSERT   new.verified                                         -> refused
--   INSERT   new.availability = 'on_job'                          -> refused
--   UPDATE   verified OR verified_at changed at all               -> refused (an immutability pin)
--   UPDATE   availability becomes 'on_job' from anything else     -> refused
--
-- This is the family the platform has already been burned by: a trust counter that could be forged
-- ([[feedback_marketplace_trust_forge_verified_only]]) and trust signals standing on nothing
-- ([[feedback_trust_signal_needs_a_living_producer]]). The guard is correct — it was simply unwatched, so
-- deleting any of the four rules would have gone unnoticed.
--
-- EVERY REFUSAL IS PAIRED WITH THE LEGITIMATE WRITE. A guard that refused every provider write would satisfy
-- all four negatives while making the product unusable, and the two positives below are what separates
-- "protects the trust columns" from "rejects providers".
begin;

insert into auth.users(id, email) values
  ('b8111111-0000-4000-8000-00000000000a','tb-trust-provider@gate.local'),
  -- the verified provider's own account: `service_provider_identity` requires a freelancer to have an
  -- auth_uid, so the fixture cannot use NULL to mean "platform-owned"
  ('b8111111-0000-4000-8000-00000000000c','tb-trust-verified@gate.local');
insert into public.hive_members(hive_id, worker_name, role, status, auth_uid) values
  ((select id from public.hives order by id limit 1),'TB Trust Provider','worker','active',
   'b8111111-0000-4000-8000-00000000000a');

-- Planted as postgres (auth.uid() null -> the vetted backend path), so the fixture itself is not what is
-- under test. Deliberately UNVERIFIED and 'online': the honest starting state for a new provider.
insert into public.service_providers(id, provider_type, auth_uid, display_name, categories,
       base_location, availability, verified) values
  ('b9222222-0000-4000-8000-00000000000a','freelancer','b8111111-0000-4000-8000-00000000000a',
   'TB Trust Co','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'online', false);

set local role authenticated;
set local request.jwt.claims = '{"sub":"b8111111-0000-4000-8000-00000000000a","role":"authenticated"}';

do $probe$
declare n int;
begin
  -- Non-vacuity: an admin would take the bypass at the top of the guard and every refusal below would vanish,
  -- so the probe would pass its positives and fail its negatives for an unrelated reason.
  raise notice 'RESULT provider_is_not_admin=%', not public.is_marketplace_admin();

  -- 1. UPDATE · the badge. Awarding yourself the trust signal buyers price against.
  begin
    update public.service_providers set verified = true
     where id = 'b9222222-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT self_verify_update=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT self_verify_update=blocked'; end;

  -- 2. UPDATE · the timestamp alone. The pin covers verified_at as well, because a badge with a forged date
  --    is a badge with a forged provenance even if the boolean is untouched.
  begin
    update public.service_providers set verified_at = now()
     where id = 'b9222222-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT self_verify_timestamp=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT self_verify_timestamp=blocked'; end;

  -- 3. UPDATE · dispatch state. Appearing busy dodges the matcher; appearing free while working oversubscribes.
  begin
    update public.service_providers set availability = 'on_job'
     where id = 'b9222222-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT self_set_on_job=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT self_set_on_job=blocked'; end;

  -- 4. INSERT · born verified. The same forgery at creation time, which is the branch a transition-shaped
  --    suite never enters (the lesson §11.16 was built on).
  begin
    insert into public.service_providers(id, provider_type, auth_uid, display_name, categories,
           base_location, availability, verified)
    values ('b9222222-0000-4000-8000-00000000000b','freelancer','b8111111-0000-4000-8000-00000000000a',
            'TB Trust Born Verified','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,
            'online', true);
    get diagnostics n = row_count;
    raise notice 'RESULT born_verified=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT born_verified=blocked'; end;

  -- 4b. INSERT · born ON_JOB, and verified=false so the BADGE rule cannot answer first. The guard tests
  --     `new.verified` before `new.availability`, so case 4 above (born verified AND online) never reached the
  --     availability clause — the mutation that allowed a born-on_job provider SURVIVED for exactly that
  --     reason. A negative has to be aimed at the clause it defends, with every earlier clause satisfied.
  begin
    insert into public.service_providers(id, provider_type, auth_uid, display_name, categories,
           base_location, availability, verified)
    values ('b9222222-0000-4000-8000-00000000000d','freelancer','b8111111-0000-4000-8000-00000000000a',
            'TB Trust Born OnJob','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,
            'on_job', false);
    get diagnostics n = row_count;
    raise notice 'RESULT born_on_job=%', case when n>0 then 'ALLOWED' else 'blocked' end;
  exception when others then raise notice 'RESULT born_on_job=blocked'; end;

  -- ── THE PERMISSIONS THAT MUST SURVIVE ────────────────────────────────────────────────────────────────
  -- 5. An ordinary profile edit by the provider themselves.
  begin
    update public.service_providers set display_name = 'TB Trust Co (renamed)'
     where id = 'b9222222-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT own_profile_edit=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT own_profile_edit=BROKEN'; end;

  -- 6. Going offline/online is the provider's OWN call — the availability rule pins only `on_job`, and a guard
  --    that pinned the whole column would quietly break the one control a provider is supposed to have.
  begin
    update public.service_providers set availability = 'offline'
     where id = 'b9222222-0000-4000-8000-00000000000a';
    get diagnostics n = row_count;
    raise notice 'RESULT own_availability_toggle=%', case when n>0 then 'works' else 'BROKEN' end;
  exception when others then raise notice 'RESULT own_availability_toggle=BROKEN'; end;
end
$probe$;

-- The trust column read BACK with the identity dropped: a refused self-verify that nevertheless left
-- `verified = true` would be the worst outcome, and every assertion above would still read `blocked`
-- ([[feedback_records_that_outlive_the_action]]).
reset role;
select set_config('request.jwt.claims', '', true);
-- THE BADGE-GRANTING PATH ITSELF, asserted as a permission rather than leaned on as a fixture. Granting
-- `verified` is only possible on the no-JWT backend path, and the first version of this cell proved that by
-- PLANTING a verified provider in the fixture — which killed the backend-branch mutation by breaking SETUP.
-- The harness labels that a weaker kill and its evidence-quality ratchet went red for it, correctly: a mutant
-- that dies because a cell could not RUN is not a mutant the bank noticed. So the same fact is asserted here
-- instead, where an assertion can object to it.
do $grant$
declare n int;
begin
  insert into public.service_providers(id, provider_type, auth_uid, display_name, categories,
         base_location, availability, verified)
  values ('b9222222-0000-4000-8000-00000000000c','freelancer','b8111111-0000-4000-8000-00000000000c',
          'TB Trust Verified Co','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'online', true);
  get diagnostics n = row_count;
  raise notice 'RESULT platform_can_grant_badge=%', case when n>0 then 'works' else 'BROKEN' end;
exception when others then raise notice 'RESULT platform_can_grant_badge=BROKEN'; end;
$grant$;

do $truth$
declare v boolean; a text;
begin
  select verified, availability into v, a from public.service_providers
   where id = 'b9222222-0000-4000-8000-00000000000a';
  raise notice 'RESULT final_verified=%', coalesce(v::text, 'null');
  raise notice 'RESULT final_availability=%', coalesce(a, 'null');
end
$truth$;

rollback;
