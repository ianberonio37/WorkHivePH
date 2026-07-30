-- TB-MK9-response-sla-honesty.sql
--
-- MK9: `marketplace.html:2398` renders **"Responds in ~Nh"** and **"N% reply rate"** straight from
-- `marketplace_sellers.response_time_h` / `response_rate`. Those are trust signals a buyer chooses a
-- seller on, and the bank recorded the cell owed because *the provenance was never verified* — the exact
-- class as the rating/sales/tier counters that turned out to stand on nothing
-- ([[feedback_trust_signal_needs_a_living_producer]]).
--
-- Checked before assuming: there IS a living producer. `trg_update_seller_response_stats` on
-- `marketplace_inquiries` recomputes both columns from the inquiry history on every insert/update. Every
-- seed value is currently NULL — not because the producer is dead, but because there are **0 inquiries**
-- in the database, and the page guards with `if (sp.response_time_h != null)` so nothing renders. That is
-- correct behaviour, and it is also why this cell could not be verified by looking: with no data the
-- assertion is vacuous either way.
--
-- So the probe MAKES the history it needs. Four inquiries with controlled timestamps, then the stored
-- figure is compared against a recomputation done independently in this file — not against itself. The
-- deltas (1h, 2h, 6h replied; one never replied) give arithmetic with a single right answer:
--
--     avg reply time = (1 + 2 + 6) / 3 = 3.0 hours
--     reply rate     = 3 replied / 4 total = 0.75
--
-- The second half asserts the honesty rule the producer's own comment states: a seller with inquiries but
-- **no replies yet** must keep BOTH columns NULL, so the UI shows "-" instead of inventing a 0% reply rate
-- that punishes a brand-new seller for having no history. A signal that lies in the empty state is worse
-- than no signal, and this is the direction a naive `COALESCE(...,0)` would break.
--
-- Self-minted, begin/rollback, nothing survives.
begin;

insert into auth.users(id, email) values
  ('d1aaaaaa-0000-4000-8000-0000000000d9','tb-mk9-seller@gate.local');
insert into public.hive_members(hive_id, worker_name, role, status, auth_uid) values
  ((select id from public.hives order by id limit 1),'TB MK9 Seller','worker','active',
   'd1aaaaaa-0000-4000-8000-0000000000d9');

insert into public.marketplace_listings
  (id, hive_id, seller_name, section, title, category, price, status)
values ('d1ffffff-0000-4000-8000-0000000000d9',
        (select id from public.hives order by id limit 1),
        'TB MK9 Seller','parts','TB MK9 listing','Tools',100,'draft');

-- Three replied inquiries with deltas of exactly 1h, 2h and 6h, and one never answered.
insert into public.marketplace_inquiries
  (id, listing_id, hive_id, buyer_name, seller_name, message, created_at, replied_at, reply_text)
values
  ('d1cccccc-0000-4000-8000-0000000000d1','d1ffffff-0000-4000-8000-0000000000d9',
   (select id from public.hives order by id limit 1),'TB MK9 Buyer','TB MK9 Seller','q1',
   now() - interval '30 hours', now() - interval '29 hours','a1'),
  ('d1cccccc-0000-4000-8000-0000000000d2','d1ffffff-0000-4000-8000-0000000000d9',
   (select id from public.hives order by id limit 1),'TB MK9 Buyer','TB MK9 Seller','q2',
   now() - interval '20 hours', now() - interval '18 hours','a2'),
  ('d1cccccc-0000-4000-8000-0000000000d3','d1ffffff-0000-4000-8000-0000000000d9',
   (select id from public.hives order by id limit 1),'TB MK9 Buyer','TB MK9 Seller','q3',
   now() - interval '10 hours', now() - interval '4 hours','a3'),
  ('d1cccccc-0000-4000-8000-0000000000d4','d1ffffff-0000-4000-8000-0000000000d9',
   (select id from public.hives order by id limit 1),'TB MK9 Buyer','TB MK9 Seller','q4',
   now() - interval '3 hours', null, null);

do $mk9$
declare
  stored_h numeric; stored_rate numeric;
  recomputed_h numeric; recomputed_rate numeric;
  n_total int; n_replied int;
begin
  select response_time_h, response_rate into stored_h, stored_rate
    from public.marketplace_sellers where worker_name = 'TB MK9 Seller';

  -- Recomputed HERE, independently of the trigger. Comparing the column to itself would prove nothing;
  -- the point is that the number a buyer reads is the number the inquiry history supports.
  select count(*), count(*) filter (where replied_at is not null)
    into n_total, n_replied
    from public.marketplace_inquiries where seller_name = 'TB MK9 Seller';
  select round(avg(extract(epoch from (replied_at - created_at)) / 3600.0)
               filter (where replied_at is not null)::numeric, 1)
    into recomputed_h
    from public.marketplace_inquiries where seller_name = 'TB MK9 Seller';
  recomputed_rate := round(n_replied::numeric / n_total::numeric, 2);

  raise notice 'RESULT inquiries_total=%',  n_total;
  raise notice 'RESULT inquiries_replied=%', n_replied;
  raise notice 'RESULT displayed_hours_matches_history=%',
    case when stored_h = recomputed_h then 'yes'
         else 'NO stored=' || coalesce(stored_h::text,'null') ||
              ' history=' || coalesce(recomputed_h::text,'null') end;
  raise notice 'RESULT displayed_rate_matches_history=%',
    case when stored_rate = recomputed_rate then 'yes'
         else 'NO stored=' || coalesce(stored_rate::text,'null') ||
              ' history=' || coalesce(recomputed_rate::text,'null') end;
  -- and pinned to the arithmetic, so a producer that "agrees with itself" while being wrong still fails
  raise notice 'RESULT displayed_hours_is_3=%', case when stored_h = 3.0 then 'yes'
    else 'NO ' || coalesce(stored_h::text,'null') end;
  raise notice 'RESULT displayed_rate_is_075=%', case when stored_rate = 0.75 then 'yes'
    else 'NO ' || coalesce(stored_rate::text,'null') end;
end
$mk9$;

-- ---- the empty state: inquiries but NO replies must stay NULL, never 0 -------------------------------
insert into public.hive_members(hive_id, worker_name, role, status, auth_uid) values
  ((select id from public.hives order by id limit 1),'TB MK9 NewSeller','worker','active',
   'd1aaaaaa-0000-4000-8000-0000000000d9');
insert into public.marketplace_listings
  (id, hive_id, seller_name, section, title, category, price, status)
values ('d1ffffff-0000-4000-8000-0000000000da',
        (select id from public.hives order by id limit 1),
        'TB MK9 NewSeller','parts','TB MK9 new listing','Tools',100,'draft');
insert into public.marketplace_inquiries
  (id, listing_id, hive_id, buyer_name, seller_name, message, created_at)
values ('d1cccccc-0000-4000-8000-0000000000d5','d1ffffff-0000-4000-8000-0000000000da',
        (select id from public.hives order by id limit 1),'TB MK9 Buyer','TB MK9 NewSeller','unanswered',
        now() - interval '2 hours');

do $empty$
declare h numeric; r numeric;
begin
  select response_time_h, response_rate into h, r
    from public.marketplace_sellers where worker_name = 'TB MK9 NewSeller';
  raise notice 'RESULT new_seller_hours_is_null=%', case when h is null then 'yes'
    else 'NO ' || h::text end;
  raise notice 'RESULT new_seller_rate_is_null=%',  case when r is null then 'yes'
    else 'NO ' || r::text end;
end
$empty$;

rollback;
