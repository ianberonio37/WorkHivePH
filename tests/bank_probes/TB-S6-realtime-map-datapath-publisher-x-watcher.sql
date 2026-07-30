-- TB-S6-realtime-map-datapath-publisher-x-watcher
--
-- The publisher x watcher data path for the live job map, proven across THREE identities inside one
-- rolled-back transaction. J29 had been walked with two WATCHERS (P-client-supervisor +
-- P-client-worker) and zero publishers, which satisfied the ">=2 personas" coverage rule while never
-- once exercising the stream ([[feedback_two_sided_journeys_need_a_role_pair]]).
--
-- Emits RESULT lines the bank's authored lane compares against the cell's `expect` block. Nothing is
-- committed; the identities are self-minted so no seeded row is borrowed.
begin;

insert into auth.users(id, email) values
  ('d1dddddd-0000-4000-8000-000000000001', 'tb-s6-client@gate.local'),
  ('d1dddddd-0000-4000-8000-000000000002', 'tb-s6-provider@gate.local'),
  ('d1dddddd-0000-4000-8000-000000000003', 'tb-s6-stranger@gate.local');

insert into public.service_providers
  (id, provider_type, auth_uid, display_name, categories, base_location, availability)
values
  ('d1eeeeee-0000-4000-8000-000000000001', 'freelancer', 'd1dddddd-0000-4000-8000-000000000002',
   'TB S6 Publisher', '{Plumbing}', 'POINT(120.5960 16.4023)'::extensions.geography, 'on_job');

-- en_route is the first state v_service_job_tracking exposes, and the state a real tracker opens in.
insert into public.service_requests
  (id, client_auth_uid, mode, custom_scope, location, status, matched_provider_id)
values
  ('d1ffffff-0000-4000-8000-000000000001', 'd1dddddd-0000-4000-8000-000000000001', 'instant',
   'tb s6 probe', 'POINT(120.5960 16.4023)'::extensions.geography, 'en_route',
   'd1eeeeee-0000-4000-8000-000000000001');

-- ── PUBLISHER: the matched provider writes live_location under their OWN identity, exactly as the
--    browser's watchPosition callback does. A service-role write here would prove nothing.
set local role authenticated;
set local request.jwt.claims = '{"sub":"d1dddddd-0000-4000-8000-000000000002","role":"authenticated"}';
update public.service_providers
   set live_location = 'POINT(120.6000 16.4100)'::extensions.geography
 where id = 'd1eeeeee-0000-4000-8000-000000000001';

-- Confirmed as the SERVICE role, deliberately. `authenticated` holds column INSERT/UPDATE on
-- service_providers but NO table SELECT - reads go through views - so a `select ... from
-- service_providers` under the provider's own JWT 42501s. The page is safe only because its write is
-- `.update({...}).eq(...)` with no `.select()`: adding one would turn a legal write into a failed
-- statement, the same shape as the phantom-create bug fixed this session
-- ([[feedback_error_on_returning_is_not_a_failed_write]]). Reading here as the service role separates
-- "the publish never landed" from "the watcher cannot see it" - two different bugs.
reset role;
select 'RESULT publisher_wrote=' || count(*)::text
  from public.service_providers
 where id = 'd1eeeeee-0000-4000-8000-000000000001' and live_location is not null;

-- ── WATCHER: the CLIENT reads that position through the tracking view.
set local role authenticated;
set local request.jwt.claims = '{"sub":"d1dddddd-0000-4000-8000-000000000001","role":"authenticated"}';
select 'RESULT watcher_sees_1=' || coalesce(round(live_lat::numeric, 4)::text, 'NONE')
  from public.v_service_job_tracking
 where request_id = 'd1ffffff-0000-4000-8000-000000000001';

-- ── MOVEMENT: the provider moves. A static render would pass a single read; only a second, DIFFERENT
--    position proves the path carries change.
reset role;
set local role authenticated;
set local request.jwt.claims = '{"sub":"d1dddddd-0000-4000-8000-000000000002","role":"authenticated"}';
update public.service_providers
   set live_location = 'POINT(120.6100 16.4200)'::extensions.geography
 where id = 'd1eeeeee-0000-4000-8000-000000000001';

reset role;
set local role authenticated;
set local request.jwt.claims = '{"sub":"d1dddddd-0000-4000-8000-000000000001","role":"authenticated"}';
select 'RESULT watcher_sees_2=' || coalesce(round(live_lat::numeric, 4)::text, 'NONE')
  from public.v_service_job_tracking
 where request_id = 'd1ffffff-0000-4000-8000-000000000001';

-- ── PRIVACY: a third identity with no relationship to the job sees NOTHING. A live location that
--    leaks is worse than one that never renders.
reset role;
set local role authenticated;
set local request.jwt.claims = '{"sub":"d1dddddd-0000-4000-8000-000000000003","role":"authenticated"}';
select 'RESULT stranger_rows=' || count(*)::text
  from public.v_service_job_tracking
 where request_id = 'd1ffffff-0000-4000-8000-000000000001';

rollback;
