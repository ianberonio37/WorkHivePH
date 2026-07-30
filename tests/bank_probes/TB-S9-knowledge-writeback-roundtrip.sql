-- TB-S9-knowledge-writeback-roundtrip
--
-- The industrial moat: an outside provider finishes a hailed job and the CLIENT'S OWN maintenance
-- logbook gains the entry. That is the whole differentiator against a generic services marketplace -
-- the work leaves knowledge behind in the hive that owns the asset.
--
-- The role-pair matters here as much as on the live map: the PROVIDER writes (by completing), the
-- CLIENT reads. Proving only that the trigger inserted a row would prove the write and skip the half
-- that has business value - and a logbook entry the client cannot see is not knowledge, it is a row.
begin;

insert into auth.users(id, email) values
  ('d3aaaaaa-0000-4000-8000-000000000001', 'tb-s9-client@gate.local'),
  ('d3aaaaaa-0000-4000-8000-000000000002', 'tb-s9-provider@gate.local'),
  ('d3aaaaaa-0000-4000-8000-000000000003', 'tb-s9-otherhive@gate.local');

insert into public.hives (id, name, invite_code, created_by)
values ('d3bbbbbb-0000-4000-8000-000000000001', 'TB S9 Hive', 'TBS9CD',
        'd3aaaaaa-0000-4000-8000-000000000001'),
       ('d3bbbbbb-0000-4000-8000-000000000002', 'TB S9 Other Hive', 'TBS9OT',
        'd3aaaaaa-0000-4000-8000-000000000003');

insert into public.hive_members (id, hive_id, auth_uid, worker_name, role, status) values
  ('d3cccccc-0000-4000-8000-000000000001', 'd3bbbbbb-0000-4000-8000-000000000001',
   'd3aaaaaa-0000-4000-8000-000000000001', 'TB S9 Client', 'supervisor', 'active'),
  ('d3cccccc-0000-4000-8000-000000000002', 'd3bbbbbb-0000-4000-8000-000000000002',
   'd3aaaaaa-0000-4000-8000-000000000003', 'TB S9 Outsider', 'supervisor', 'active');

insert into public.service_providers
  (id, provider_type, auth_uid, display_name, categories, base_location, availability)
values ('d3dddddd-0000-4000-8000-000000000001', 'freelancer', 'd3aaaaaa-0000-4000-8000-000000000002',
        'TB S9 Provider', '{Plumbing}', 'POINT(120.5960 16.4023)'::extensions.geography, 'on_job');

-- The composer prefixes an asset-context hail with [ASSET-TAG]; the writeback reuses that prefix as
-- the logbook's `machine`, which is what links the entry to the physical asset.
insert into public.service_requests
  (id, client_auth_uid, client_worker_name, hive_id, mode, custom_scope, location, address,
   status, matched_provider_id)
values ('d3eeeeee-0000-4000-8000-000000000001', 'd3aaaaaa-0000-4000-8000-000000000001',
        'TB S9 Client', 'd3bbbbbb-0000-4000-8000-000000000001', 'instant',
        '[PUMP-207] leaking mechanical seal', 'POINT(120.5960 16.4023)'::extensions.geography,
        'Plant 2, Baguio', 'in_progress', 'd3dddddd-0000-4000-8000-000000000001');

-- ── WRITER: the PROVIDER completes the job under their own identity. A service-role UPDATE here
--    would prove the trigger fires but not that the person who can fire it is the provider.
set local role authenticated;
set local request.jwt.claims = '{"sub":"d3aaaaaa-0000-4000-8000-000000000002","role":"authenticated"}';
update public.service_requests set status = 'completed'
 where id = 'd3eeeeee-0000-4000-8000-000000000001';
select 'RESULT provider_completed=' || count(*)::text
  from public.service_requests
 where id = 'd3eeeeee-0000-4000-8000-000000000001' and status = 'completed';

-- ── READER: the CLIENT sees the entry in their own logbook, under their own JWT, through RLS.
reset role;
set local role authenticated;
set local request.jwt.claims = '{"sub":"d3aaaaaa-0000-4000-8000-000000000001","role":"authenticated"}';
select 'RESULT client_sees_entries=' || count(*)::text
  from public.logbook
 where hive_id = 'd3bbbbbb-0000-4000-8000-000000000001'
   and action like '%d3eeeeee-0000-4000-8000-000000000001%';

-- The asset linkage is the point: an entry with no machine is a note, not maintenance history.
select 'RESULT machine_tag=' || coalesce(max(machine), 'NONE')
  from public.logbook
 where hive_id = 'd3bbbbbb-0000-4000-8000-000000000001'
   and action like '%d3eeeeee-0000-4000-8000-000000000001%';

-- The provider is NAMED in the entry: six months later the hive must be able to tell who touched the
-- asset without re-opening the marketplace.
select 'RESULT names_provider=' || count(*)::text
  from public.logbook
 where hive_id = 'd3bbbbbb-0000-4000-8000-000000000001'
   and action like '%TB S9 Provider%';

select 'RESULT entry_status=' || coalesce(max(status), 'NONE')
  from public.logbook
 where hive_id = 'd3bbbbbb-0000-4000-8000-000000000001'
   and action like '%d3eeeeee-0000-4000-8000-000000000001%';

-- ── TENANT: a supervisor of a DIFFERENT hive must not read this hive's maintenance history. The
--    writeback crosses an organisational boundary (an outside provider's work landing inside a hive),
--    which is exactly where isolation is easiest to get wrong.
reset role;
set local role authenticated;
set local request.jwt.claims = '{"sub":"d3aaaaaa-0000-4000-8000-000000000003","role":"authenticated"}';
select 'RESULT outsider_sees=' || count(*)::text
  from public.logbook
 where action like '%d3eeeeee-0000-4000-8000-000000000001%';

-- ── IDEMPOTENCE: the id is derived from the request id, so a re-fired completion must not append a
--    second entry. A duplicated maintenance record corrupts every MTBF/MTTR figure computed from it.
--    Re-fired as the PROVIDER, because that is the real shape of this risk - a double-tapped "Mark
--    complete" or a retried request - not a system replay. `reset role` alone would NOT do it:
--    resetting the role leaves request.jwt.claims set, so the write would arrive as whichever identity
--    spoke last (here the outsider) and be refused for the wrong reason entirely.
reset role;
set local role authenticated;
set local request.jwt.claims = '{"sub":"d3aaaaaa-0000-4000-8000-000000000002","role":"authenticated"}';
--    The re-fire must be ACCEPTED for this to prove anything: if the guard refused the second write,
--    "no duplicate appeared" would be vacuous - the trigger never ran.
with r as (update public.service_requests set status = 'completed'
            where id = 'd3eeeeee-0000-4000-8000-000000000001' returning id)
select 'RESULT refire_accepted=' || count(*)::text from r;

--    Counted back as the CLIENT. Counting under the PROVIDER's JWT returned 0 - not because no
--    duplicate existed but because the provider is not a hive member and RLS hides every logbook row
--    from them. An assertion run under the wrong identity measures RLS, not the invariant, and reads
--    as a clean pass either way ([[feedback_verify_the_instrument_before_the_page]]).
reset role;
set local role authenticated;
set local request.jwt.claims = '{"sub":"d3aaaaaa-0000-4000-8000-000000000001","role":"authenticated"}';
select 'RESULT entries_after_refire=' || count(*)::text
  from public.logbook
 where action like '%d3eeeeee-0000-4000-8000-000000000001%';

rollback;
