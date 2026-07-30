-- TB-S5-edge-push-audience-selection
--
-- WHO receives the broadcast push. The registered `outbox-delivery` gate already proves the other half
-- of this layer - that a caller exists and that enqueue -> relay -> 2xx -> done completes - but it
-- hand-builds its probe payload (`select id from service_providers where availability='online' limit
-- 1`), so it never executes fanout_broadcast_push's own audience query. A fan-out that paged offline
-- providers, providers 90km away, providers of the wrong trade, or the client's OWN provider profile
-- would pass that gate green while spamming the wrong phones.
--
-- A push interrupts a person. The browse feed may widen its radius because scrolling a longer list is
-- harmless; the fan-out may not.
--
-- Five providers are planted, one eligible and four each disqualified by exactly ONE rule, so a
-- failure names the rule that broke.
begin;

insert into auth.users(id, email) values
  ('d2aaaaaa-0000-4000-8000-000000000001', 'tb-s5-client@gate.local'),
  ('d2aaaaaa-0000-4000-8000-000000000002', 'tb-s5-eligible@gate.local'),
  ('d2aaaaaa-0000-4000-8000-000000000003', 'tb-s5-offline@gate.local'),
  ('d2aaaaaa-0000-4000-8000-000000000004', 'tb-s5-wrongcat@gate.local'),
  ('d2aaaaaa-0000-4000-8000-000000000005', 'tb-s5-faraway@gate.local');

insert into public.service_catalog (id, segment, category, name, unit, base_rate, active)
values ('d2bbbbbb-0000-4000-8000-000000000001', 'consumer', 'TBPlumbing',
        'TB probe job', 'per_visit', 1000, true);

-- id ....01 ELIGIBLE  : online · category matches · 0 m away · not the client
-- id ....02 OFFLINE   : the only difference is availability
-- id ....03 WRONG CAT : online and near, but does not do this trade
-- id ....04 FAR AWAY  : online and right trade, ~96 km out (radius is 5 km)
-- id ....05 SELF      : the CLIENT's own provider profile - never ping someone with their own hail
insert into public.service_providers
  (id, provider_type, auth_uid, display_name, categories, base_location, availability)
values
  ('d2cccccc-0000-4000-8000-000000000001', 'freelancer', 'd2aaaaaa-0000-4000-8000-000000000002',
   'TB Eligible',  '{TBPlumbing}', 'POINT(120.5960 16.4023)'::extensions.geography, 'online'),
  ('d2cccccc-0000-4000-8000-000000000002', 'freelancer', 'd2aaaaaa-0000-4000-8000-000000000003',
   'TB Offline',   '{TBPlumbing}', 'POINT(120.5960 16.4023)'::extensions.geography, 'offline'),
  ('d2cccccc-0000-4000-8000-000000000003', 'freelancer', 'd2aaaaaa-0000-4000-8000-000000000004',
   'TB WrongCat',  '{TBWelding}',  'POINT(120.5960 16.4023)'::extensions.geography, 'online'),
  ('d2cccccc-0000-4000-8000-000000000004', 'freelancer', 'd2aaaaaa-0000-4000-8000-000000000005',
   'TB FarAway',   '{TBPlumbing}', 'POINT(121.5000 16.4023)'::extensions.geography, 'online'),
  ('d2cccccc-0000-4000-8000-000000000005', 'freelancer', 'd2aaaaaa-0000-4000-8000-000000000001',
   'TB SelfHail',  '{TBPlumbing}', 'POINT(120.5960 16.4023)'::extensions.geography, 'online');

-- The hail is born broadcasting: trg_fanout_broadcast_push is AFTER INSERT OR UPDATE OF status, and
-- the function returns early unless this write is the transition INTO broadcasting.
insert into public.service_requests
  (id, client_auth_uid, mode, catalog_item_id, location, address, urgency,
   broadcast_radius_m, status)
values
  ('d2dddddd-0000-4000-8000-000000000001', 'd2aaaaaa-0000-4000-8000-000000000001', 'instant',
   'd2bbbbbb-0000-4000-8000-000000000001', 'POINT(120.5960 16.4023)'::extensions.geography,
   'Probe St, Baguio', 'normal', 5000, 'broadcasting');

select 'RESULT outbox_rows=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push' and payload->>'body' like 'TB probe job%';

select 'RESULT eligible_in_payload=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push' and payload->>'body' like 'TB probe job%'
   and payload->'provider_ids' ? 'd2cccccc-0000-4000-8000-000000000001';

select 'RESULT offline_in_payload=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push' and payload->'provider_ids' ? 'd2cccccc-0000-4000-8000-000000000002';

select 'RESULT wrongcat_in_payload=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push' and payload->'provider_ids' ? 'd2cccccc-0000-4000-8000-000000000003';

select 'RESULT faraway_in_payload=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push' and payload->'provider_ids' ? 'd2cccccc-0000-4000-8000-000000000004';

select 'RESULT selfhail_in_payload=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push' and payload->'provider_ids' ? 'd2cccccc-0000-4000-8000-000000000005';

-- The audience is the WHOLE audience, not "at least the right one": exactly one recipient here.
select 'RESULT recipient_count=' ||
       coalesce((select jsonb_array_length(payload->'provider_ids') from public.service_outbox
                  where consumer = 'notify-push' and payload->>'body' like 'TB probe job%'
                  limit 1)::text, 'NONE');

-- The urgency wording is part of the payload contract the service worker renders. It is asserted
-- here because the branch used to test `urgency = 'emergency'`, a value the CHECK forbids
-- ({low, normal, high, critical}) - so a CRITICAL "production is down" hail pushed with the same
-- words as a whenever-convenient one, and nothing ever failed (mig 20260729000017).
select 'RESULT title=' ||
       coalesce((select payload->>'title' from public.service_outbox
                  where consumer = 'notify-push' and payload->>'body' like 'TB probe job%'
                  limit 1), 'NONE');

-- The urgent branch must be REACHABLE. Asserting only the calm title would have passed happily
-- while the urgent one was dead code.
insert into public.service_requests
  (id, client_auth_uid, mode, catalog_item_id, location, address, urgency,
   broadcast_radius_m, status)
values
  ('d2dddddd-0000-4000-8000-000000000002', 'd2aaaaaa-0000-4000-8000-000000000001', 'instant',
   'd2bbbbbb-0000-4000-8000-000000000001', 'POINT(120.5960 16.4023)'::extensions.geography,
   'Critical St, Baguio', 'critical', 5000, 'broadcasting');
select 'RESULT critical_title=' ||
       coalesce((select payload->>'title' from public.service_outbox
                  where consumer = 'notify-push'
                    and payload->>'body' like '%Critical St%' limit 1), 'NONE');
select 'RESULT outbox_rows_after_critical=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push' and payload->>'body' like 'TB probe job%';

-- RE-FIRE: writing 'broadcasting' onto a row that is ALREADY broadcasting fires the trigger again.
-- The function must return early - a duplicate push for the same hail is the notification equivalent
-- of a double-submit, and every re-touch would repeat it.
update public.service_requests set status = 'broadcasting'
 where id = 'd2dddddd-0000-4000-8000-000000000001';
select 'RESULT rows_after_refire=' || count(*)::text
  from public.service_outbox
 where consumer = 'notify-push' and payload->>'body' like 'TB probe job%';
-- 2 = the normal hail + the critical one, and NOT a third from the re-fire.

rollback;
