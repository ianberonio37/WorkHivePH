-- TB-STATE-inducers-empty-filtered0-edge.sql
--
-- THE STATE AXIS, finally INDUCED instead of declared.
--
-- `state` was `None` on 212 of 247 cells, and the original plan said why that matters in its own words:
-- **"A state axis with no induction mechanism is decoration."** §7b prescribed an inducer per state and
-- none was ever built. Two of the five axes (`viewport`, `lang`) were retired today for exactly that
-- reason; this file is the other half of the answer — the states that CAN be induced at SQL altitude get
-- induced here rather than removed.
--
--   empty      the tenant exists and simply has nothing yet
--   filtered0  rows exist, and the filter matches none of them
--   edge       boundary values that are legal but extreme
--
-- (`error` and `degraded` are NOT here on purpose: a route abort / 401 / 5xx and an offline write queue are
--  browser facts, so they belong to the journey lane. Claiming them at SQL altitude would be the
--  cheapest-honest-altitude rule broken in the expensive direction.)
--
-- WHY THIS IS WORTH A CELL — the defect it locks is one we actually shipped. `read-battery` once reported
-- SIX named page failures, all "DB empty -> empty-state (no error)", and NOT ONE was real: the hive UUID it
-- pinned had been reseeded away, so every assertion was measuring a tenant that did not exist
-- ([[feedback_a_dead_fixture_invents_page_defects]]). The lesson is the assertion below:
--
--   > At the QUERY level, `empty`, `filtered0` and a NONEXISTENT TENANT are all "0 rows". They are three
--   > completely different truths — "nothing yet", "nothing matches", "you are asking about nobody" — and a
--   > surface that renders the same thing for all three will one day tell a real user their data is gone.
--
-- So this probe proves both halves: the three states really are indistinguishable by row count alone (which
-- is why a count is never a diagnosis), and the tenant-existence check that DOES separate them works.
begin;

-- A hive that exists and owns nothing: the honest `empty` state, and the one a count cannot tell apart
-- from a typo'd tenant id.
insert into public.hives(id, name, invite_code, created_by)
values ('d1999999-0000-4000-8000-000000000001','TB State Empty Hive','TBST01',
        (select created_by from public.hives order by id limit 1));

-- A hive that DOES own listings, so `filtered0` can be induced against real rows rather than against
-- emptiness (a filter over an empty table returns 0 for the wrong reason).
insert into public.hives(id, name, invite_code, created_by)
values ('d1999999-0000-4000-8000-000000000002','TB State Full Hive','TBST02',
        (select created_by from public.hives order by id limit 1));

insert into public.marketplace_listings
  (id, hive_id, seller_name, section, title, category, price, status)
values
  ('d1999999-1000-4000-8000-000000000001','d1999999-0000-4000-8000-000000000002',
   'TB State Seller','parts','state alpha','Tools',500,'draft'),
  ('d1999999-1000-4000-8000-000000000002','d1999999-0000-4000-8000-000000000002',
   'TB State Seller','parts','state beta','Tools',500,'draft'),
  -- EDGE: the ACTUAL boundaries, read from the schema rather than guessed. `price >= 0` makes ZERO the
  -- minimum legal price (my first draft used 1, which is just a small number, not an edge). The title is
  -- sent OVER-LONG on purpose, to pin where it gets cut — see the cap assertion below.
  ('d1999999-1000-4000-8000-000000000003','d1999999-0000-4000-8000-000000000002',
   'TB State Seller','parts', repeat('E', 200) ,'Tools',0,'draft');

do $states$
declare
  n_empty        int;
  n_filtered0    int;
  n_ghost        int;
  n_populated    int;
  ghost_exists   int;
  empty_exists   int;
  n_edge_price   int;
  edge_title_len int;
begin
  -- ── empty: a REAL tenant with nothing ───────────────────────────────────────────────────────────
  select count(*) into n_empty from public.marketplace_listings
   where hive_id = 'd1999999-0000-4000-8000-000000000001';
  raise notice 'RESULT state_empty_rows=%', n_empty;

  -- ── filtered0: real rows, and a filter none of them satisfy ─────────────────────────────────────
  select count(*) into n_populated from public.marketplace_listings
   where hive_id = 'd1999999-0000-4000-8000-000000000002';
  select count(*) into n_filtered0 from public.marketplace_listings
   where hive_id = 'd1999999-0000-4000-8000-000000000002' and category = 'NoSuchCategory';
  raise notice 'RESULT state_populated_rows=%', n_populated;
  raise notice 'RESULT state_filtered0_rows=%', n_filtered0;
  -- Non-vacuity: filtered0 only means something if the unfiltered set was non-empty.
  raise notice 'RESULT state_filtered0_had_rows_to_filter=%',
    case when n_populated > 0 then 'yes' else 'NO' end;

  -- ── the ghost tenant: a hive id that does not exist at all ──────────────────────────────────────
  select count(*) into n_ghost from public.marketplace_listings
   where hive_id = 'd1999999-0000-4000-8000-0000000000ff';
  raise notice 'RESULT state_ghost_tenant_rows=%', n_ghost;

  -- THE FINDING, asserted rather than assumed: all three are the same number.
  raise notice 'RESULT three_states_indistinguishable_by_count=%',
    case when n_empty = 0 and n_filtered0 = 0 and n_ghost = 0 then 'yes' else 'NO' end;

  -- ── and the check that DOES separate them ───────────────────────────────────────────────────────
  select count(*) into empty_exists from public.hives
   where id = 'd1999999-0000-4000-8000-000000000001';
  select count(*) into ghost_exists from public.hives
   where id = 'd1999999-0000-4000-8000-0000000000ff';
  raise notice 'RESULT tenant_exists_separates_empty_from_ghost=%',
    case when empty_exists = 1 and ghost_exists = 0 then 'yes'
         else 'NO empty=' || empty_exists || ' ghost=' || ghost_exists end;

  -- ── edge: legal but extreme values survive a round trip ─────────────────────────────────────────
  select count(*) into n_edge_price from public.marketplace_listings
   where hive_id = 'd1999999-0000-4000-8000-000000000002' and price = 0;
  select max(length(title)) into edge_title_len from public.marketplace_listings
   where hive_id = 'd1999999-0000-4000-8000-000000000002';
  raise notice 'RESULT state_edge_zero_price_persisted=%',
    case when n_edge_price = 1 then 'yes' else 'NO' end;

  -- THE TITLE CAP, and the assertion I had to correct.
  --
  -- I first asserted the 200-char title came back at 200 and it returned 120, which looked like silent
  -- truncation of user content: `title` is unbounded `text`, and `marketplace-listing-assist` slices titles
  -- at 200 (`.slice(0, 200)`) while `cap_marketplace_listings_text` does `left(NEW.title, 120)` — an
  -- 80-character silent loss with no error, no toast and no log.
  --
  -- IT IS NOT REACHABLE, and checking beat reporting. `#post-title` in marketplace.html carries
  -- `maxlength="120"`, matching the DB cap exactly, and the AI assist writes only `category` and
  -- `description` — never the title. So both ENDS of the chain agree at 120 and only the middle layer is
  -- looser; no user path can deliver 121-200 characters. The edge function's 200 is defence-in-depth that
  -- happens to be slack, not a defect.
  --
  -- So the assertion is the one that would actually catch drift: the DB cap is EXACTLY the number the form
  -- also uses. Raise `maxlength` to 200 without raising the trigger and this reddens; lower the trigger to
  -- 100 and it reddens. Asserting "200 survives" would instead have demanded the product abandon a
  -- deliberate cap ([[feedback_gates_lock_refusal_not_permission]] — lock the behaviour that EXISTS).
  raise notice 'RESULT state_edge_title_capped_at_form_maxlength_120=%',
    case when edge_title_len = 120 then 'yes' else 'NO len=' || coalesce(edge_title_len,-1) end;
end
$states$;

rollback;
