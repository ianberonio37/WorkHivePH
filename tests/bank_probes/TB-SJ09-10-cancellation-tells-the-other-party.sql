-- TB-SJ09-10-cancellation-tells-the-other-party
--
-- The role-pair rule found this one, and the missing half was missing from the PRODUCT.
-- `SJ-J09-cancel-client` and `SJ-J10-cancel-provider` were both walk-complete having been walked only
-- from the CANCELLER's side. A cancellation is only meaningful to the person it strands, and a search
-- of every function touching the cancelled states returned exactly two - the availability sync and the
-- status guard. Nothing told anybody.
--
-- Concretely: a client cancels while the provider is EN ROUTE. The provider's availability flips back
-- to 'online', the job vanishes from their list, and they keep driving to a site for work that no
-- longer exists. Migration 20260729000018 wires both directions onto the push rail that already
-- carries "New job nearby".
--
-- Asserted here at SQL altitude: the enqueue is transactional with the state change, it names the
-- RIGHT party in each direction, it says something a person can act on, and it does not fire twice.
begin;

insert into auth.users(id, email) values
  ('d8aaaaaa-0000-4000-8000-000000000001', 'tb-c1-client@gate.local'),
  ('d8aaaaaa-0000-4000-8000-000000000002', 'tb-c1-provider@gate.local'),
  ('d8aaaaaa-0000-4000-8000-000000000003', 'tb-c2-client@gate.local'),
  ('d8aaaaaa-0000-4000-8000-000000000004', 'tb-c2-provider@gate.local');

insert into public.service_providers
  (id, provider_type, auth_uid, display_name, categories, base_location, availability)
values
  ('d8bbbbbb-0000-4000-8000-000000000001', 'freelancer', 'd8aaaaaa-0000-4000-8000-000000000002',
   'TB Cancel Prov A', '{Plumbing}', 'POINT(120.5960 16.4023)'::extensions.geography, 'on_job'),
  ('d8bbbbbb-0000-4000-8000-000000000002', 'freelancer', 'd8aaaaaa-0000-4000-8000-000000000004',
   'TB Cancel Prov B', '{Plumbing}', 'POINT(120.5960 16.4023)'::extensions.geography, 'on_job');

-- Direction 1: the CLIENT cancels a job the provider is already en route to. This is the harmful one.
insert into public.service_requests
  (id, client_auth_uid, client_worker_name, mode, custom_scope, location, address, status,
   matched_provider_id)
values ('d8cccccc-0000-4000-8000-000000000001', 'd8aaaaaa-0000-4000-8000-000000000001', 'TB Client A',
        'instant', 'tb cancel probe A', 'POINT(120.5960 16.4023)'::extensions.geography,
        'Plant 4, Baguio', 'en_route', 'd8bbbbbb-0000-4000-8000-000000000001');

set local role authenticated;
set local request.jwt.claims = '{"sub":"d8aaaaaa-0000-4000-8000-000000000001","role":"authenticated"}';
update public.service_requests set status = 'cancelled_by_client'
 where id = 'd8cccccc-0000-4000-8000-000000000001';
reset role;
reset request.jwt.claims;

select 'RESULT client_cancel_notified=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push' and payload->>'title' = 'Job cancelled'
   and payload->'auth_uids' ? 'd8aaaaaa-0000-4000-8000-000000000002';

-- The PROVIDER is told, and the CLIENT is not paged about their own action.
select 'RESULT client_not_paged_own_cancel=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push'
   and payload->'auth_uids' ? 'd8aaaaaa-0000-4000-8000-000000000001';

-- The message has to be actionable. "Job cancelled" alone leaves a provider mid-drive guessing.
select 'RESULT tells_them_to_stand_down=' ||
       case when count(*) > 0 then 'yes' else 'no' end
  from public.service_outbox
 where consumer = 'notify-push' and payload->>'title' = 'Job cancelled'
   and payload->>'body' like '%do not travel%';

-- Direction 2: the PROVIDER cancels; the CLIENT is the stranded party.
insert into public.service_requests
  (id, client_auth_uid, client_worker_name, mode, custom_scope, location, status, matched_provider_id)
values ('d8cccccc-0000-4000-8000-000000000002', 'd8aaaaaa-0000-4000-8000-000000000003', 'TB Client B',
        'instant', 'tb cancel probe B', 'POINT(120.5960 16.4023)'::extensions.geography,
        'accepted', 'd8bbbbbb-0000-4000-8000-000000000002');

set local role authenticated;
set local request.jwt.claims = '{"sub":"d8aaaaaa-0000-4000-8000-000000000004","role":"authenticated"}';
update public.service_requests set status = 'cancelled_by_provider'
 where id = 'd8cccccc-0000-4000-8000-000000000002';
reset role;
reset request.jwt.claims;

select 'RESULT provider_cancel_notified_client=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push' and payload->>'title' = 'Provider cancelled'
   and payload->'auth_uids' ? 'd8aaaaaa-0000-4000-8000-000000000003';

-- It names WHO cancelled: "someone cancelled" is not a thing a person can act on.
select 'RESULT names_the_provider=' || case when count(*) > 0 then 'yes' else 'no' end
  from public.service_outbox
 where consumer = 'notify-push' and payload->>'body' like '%TB Cancel Prov B%';

-- NO DOUBLE FIRE: re-writing the same cancelled status must not enqueue a second notice. A duplicate
-- cancellation push is worse than none - the second one implies a second job.
update public.service_requests set status = 'cancelled_by_client'
 where id = 'd8cccccc-0000-4000-8000-000000000001';
-- Scoped to THIS probe's two jobs. Counting every cancellation notice in the outbox measured the
-- whole platform: the browser cells cancel real jobs and their notices are a legitimate product
-- side-effect, so the number drifted with unrelated activity.
select 'RESULT notices_after_refire=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push' and payload->>'title' in ('Job cancelled', 'Provider cancelled')
   and payload->>'body' like '%tb cancel probe%';

-- A hail cancelled while still BROADCASTING was never anyone's job: nobody is paged.
insert into public.service_requests
  (id, client_auth_uid, mode, custom_scope, location, status)
values ('d8cccccc-0000-4000-8000-000000000003', 'd8aaaaaa-0000-4000-8000-000000000001', 'instant',
        'tb cancel probe C', 'POINT(120.5960 16.4023)'::extensions.geography, 'broadcasting');
update public.service_requests set status = 'cancelled_by_client'
 where id = 'd8cccccc-0000-4000-8000-000000000003';
-- Scoped to CANCELLATION notices by title. The first cut matched any push whose body carried this
-- scope and returned 1 - the "New job nearby" the broadcast fan-out enqueued when the row was born
-- broadcasting. It was measuring a different trigger's correct behaviour and calling it a failure.
select 'RESULT unmatched_cancel_pages_nobody=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push'
   and payload->>'title' in ('Job cancelled', 'Provider cancelled')
   and payload->>'body' like '%tb cancel probe C%';

-- ...and the broadcast push for that same row IS still there, which is what makes the 0 above a real
-- absence rather than an empty table.
select 'RESULT broadcast_push_still_present=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push' and payload->>'title' like '%job nearby%'
   and payload->>'body' like '%tb cancel probe C%';

rollback;
