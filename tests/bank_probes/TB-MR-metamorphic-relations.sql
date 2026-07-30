-- TB-MR-metamorphic-relations.sql
--
-- METAMORPHIC RELATIONS — an oracle for the surfaces that never had one.
--
-- WHY THIS EXISTS. The bank's oracle mix was 194 `refusal` of 247 cells, 35 `db-truth`, 10 `rubric`,
-- 7 `continuity` and exactly ONE `eval`. That is not an accident of effort: wherever we could not write
-- down an exact expected value, we either skipped the surface or graded it with a rubric. Ranking, filtering
-- and permission-visibility are all in that bucket — the "right" result set depends on live data nobody
-- froze.
--
-- A metamorphic relation is *"a necessary property of the intended functionality that MUST involve MULTIPLE
-- EXECUTIONS of the software"* (substrate/external/external-metamorphic-testing-oracle-problem-*.md). You
-- never need the right answer — only a relation the right answers must obey. The canonical published
-- example is literally our shape: a search returning 1,671 results, then filtered by price or star rating,
-- **"should return a subset of the previous results."**
--
-- Three MRs run here, all at SQL altitude because all three are database facts:
--
--   MR1  FILTER SUBSET          a filtered listing set is a SUBSET of the unfiltered one.
--   MR2  PERMISSION MONOTONICITY a member sees a SUBSET of what a supervisor sees on the same hive.
--   MR3  ORDER-INDEPENDENT CREDIT verifying two top-ups in either order reaches the SAME balance.
--
-- MR2 is the one worth pausing on: the authority axis today is 100% refusal cells — "this actor must be
-- refused" — which can all pass on a system that shows NOBODY anything. Monotonicity is a POSITIVE
-- statement about the same axis that a fail-closed system cannot satisfy vacuously... and the probe proves
-- that non-vacuously by asserting the supervisor's set is non-empty before comparing.
--
-- MR3 is commutativity on the money path. `verify` mints a ledger row, so if order mattered, one ordering
-- would produce a different balance than the other and the credit a provider can spend would depend on the
-- sequence the founder happened to click. No expected balance is written down anywhere in this file — only
-- that the two orderings agree, and that both actually minted.
--
-- Self-minted identities, begin/rollback, nothing survives. RESULT lines are emitted via RAISE NOTICE
-- because the reads sit inside exception-guarded blocks.
begin;

insert into auth.users(id, email) values
  ('d1a11111-0000-4000-8000-000000000001','tb-mr-sup@gate.local'),
  ('d1a11111-0000-4000-8000-000000000002','tb-mr-member@gate.local'),
  ('d1a11111-0000-4000-8000-000000000003','tb-mr-admin@gate.local');

-- ── MR1 · FILTER SUBSET ─────────────────────────────────────────────────────────────────────────────
-- Three listings in one section, two categories, two price points. The relation must hold for EVERY
-- filter, so the probe checks a category filter and a price filter independently.
insert into public.marketplace_listings
  (id, hive_id, seller_name, section, title, category, price, status)
values
  ('d1f11111-0000-4000-8000-000000000001',(select id from public.hives order by id limit 1),
   'TB MR Seller','parts','MR alpha','Tools',100,'draft'),
  ('d1f11111-0000-4000-8000-000000000002',(select id from public.hives order by id limit 1),
   'TB MR Seller','parts','MR beta','Tools',900,'draft'),
  ('d1f11111-0000-4000-8000-000000000003',(select id from public.hives order by id limit 1),
   'TB MR Seller','parts','MR gamma','Safety',100,'draft');

do $mr1$
declare
  unfiltered uuid[]; by_cat uuid[]; by_price uuid[];
begin
  select array_agg(id order by id) into unfiltered from public.marketplace_listings
   where title like 'MR %';
  select array_agg(id order by id) into by_cat from public.marketplace_listings
   where title like 'MR %' and category = 'Tools';
  select array_agg(id order by id) into by_price from public.marketplace_listings
   where title like 'MR %' and price <= 100;

  -- `<@` is array containment: "every element of the filtered set is in the unfiltered set".
  raise notice 'RESULT mr1_category_is_subset=%',
    case when by_cat <@ unfiltered then 'yes' else 'NO' end;
  raise notice 'RESULT mr1_price_is_subset=%',
    case when by_price <@ unfiltered then 'yes' else 'NO' end;
  -- NON-VACUITY: a filter that returns nothing is trivially a subset. The relation only means something
  -- if the filter actually kept rows and actually removed some.
  raise notice 'RESULT mr1_filter_kept_rows=%',
    case when coalesce(array_length(by_cat,1),0) > 0 then 'yes' else 'NO' end;
  raise notice 'RESULT mr1_filter_removed_rows=%',
    case when coalesce(array_length(by_cat,1),0) < coalesce(array_length(unfiltered,1),0)
         then 'yes' else 'NO' end;
end
$mr1$;

-- ── MR2 · PERMISSION MONOTONICITY ───────────────────────────────────────────────────────────────────
-- Same hive: a plain member's visible request set must be a SUBSET of a supervisor's. This is a POSITIVE
-- assertion on the authority axis, which is otherwise entirely refusal cells.
insert into public.hive_members(hive_id, worker_name, role, status, auth_uid) values
  ((select id from public.hives order by id limit 1),'TB MR Sup','supervisor','active',
   'd1a11111-0000-4000-8000-000000000001'),
  ((select id from public.hives order by id limit 1),'TB MR Member','worker','active',
   'd1a11111-0000-4000-8000-000000000002');

-- TWO requests, deliberately shaped so the two sets DIFFER. `service_requests_party_read` grants
-- visibility via (a) being the client, (b) active membership of the row's hive, or (c) being the matched
-- provider. So:
--   R1  client = the supervisor, hive_id = NULL  -> visible to the supervisor ONLY (path a)
--   R2  client = the supervisor, hive_id = set   -> visible to BOTH (the member via path b)
--
-- My first draft gave both requests a hive_id, which made the two sets IDENTICAL — subset would then hold
-- by equality and the relation would be satisfied without any permission difference existing. A
-- metamorphic relation that cannot distinguish "correctly narrower" from "identical" is decoration, which
-- is exactly what this arc removed from the axes list an hour ago.
insert into public.service_requests(id, client_auth_uid, mode, custom_scope, location, status, hive_id)
values
  ('d1c11111-0000-4000-8000-000000000001','d1a11111-0000-4000-8000-000000000001','instant',
   'mr private to the supervisor','POINT(120.5960 16.4023)'::extensions.geography,'broadcasting', null),
  ('d1c11111-0000-4000-8000-000000000002','d1a11111-0000-4000-8000-000000000001','instant',
   'mr shared with the hive','POINT(120.5960 16.4023)'::extensions.geography,'broadcasting',
   (select id from public.hives order by id limit 1));

do $mr2$
declare sup_ids uuid[]; mem_ids uuid[];
begin
  set local role authenticated;
  set local request.jwt.claims = '{"sub":"d1a11111-0000-4000-8000-000000000001","role":"authenticated"}';
  select array_agg(id order by id) into sup_ids from public.service_requests;

  set local request.jwt.claims = '{"sub":"d1a11111-0000-4000-8000-000000000002","role":"authenticated"}';
  select array_agg(id order by id) into mem_ids from public.service_requests;
  reset role;

  raise notice 'RESULT mr2_member_subset_of_supervisor=%',
    case when coalesce(mem_ids,'{}') <@ coalesce(sup_ids,'{}') then 'yes' else 'NO' end;
  -- NON-VACUOUS #1: a system that shows nobody anything satisfies monotonicity trivially, and every
  -- refusal cell in the bank would pass on it too. Require the supervisor to actually see something.
  raise notice 'RESULT mr2_supervisor_sees_something=%',
    case when coalesce(array_length(sup_ids,1),0) > 0 then 'yes' else 'NO' end;
  -- NON-VACUOUS #2: and require the subset to be STRICT. Equal sets satisfy `<@` while proving no
  -- permission boundary exists at all - the weak version of this MR that the fixture above was rebuilt to
  -- rule out.
  raise notice 'RESULT mr2_subset_is_strict=%',
    case when coalesce(array_length(mem_ids,1),0) < coalesce(array_length(sup_ids,1),0)
         then 'yes' else 'NO mem=' || coalesce(array_length(mem_ids,1),0)
                        || ' sup=' || coalesce(array_length(sup_ids,1),0) end;
end
$mr2$;

-- CLEAR THE IDENTITY, not just the role. `set local request.jwt.claims` inside a DO block is
-- TRANSACTION-scoped, not block-scoped: `reset role` above restores the role but leaves auth.uid()
-- returning the member. MR3 below expects the service-role/system path (auth.uid() IS NULL, the branch
-- that MINTS), and without this line the top-up guard correctly refused its own fixture with
-- "payer_auth_uid must be the caller" - a probe accusing the product of a bug in the probe's own setup.
set local request.jwt.claims = '';

-- ── MR3 · ORDER-INDEPENDENT CREDIT ──────────────────────────────────────────────────────────────────
-- Two top-ups for one provider account, verified in BOTH orders inside savepoints. The balance must agree.
-- No expected balance appears in this file.
insert into public.service_providers(id, provider_type, auth_uid, display_name, categories,
       base_location, availability)
values ('d1b11111-0000-4000-8000-000000000002','freelancer','d1a11111-0000-4000-8000-000000000003',
        'TB MR Payee','{Plumbing}','POINT(120.5960 16.4023)'::extensions.geography,'online');

insert into public.service_credit_topups
  (id, account_type, account_id, payer_auth_uid, amount, gcash_ref, status)
values
  ('d1aa1111-0000-4000-8000-000000000001','provider','d1b11111-0000-4000-8000-000000000002',
   'd1a11111-0000-4000-8000-000000000003',500,'910000000001','pending_verification'),
  ('d1aa1111-0000-4000-8000-000000000002','provider','d1b11111-0000-4000-8000-000000000002',
   'd1a11111-0000-4000-8000-000000000003',250,'910000000002','pending_verification');

-- A nested BEGIN..EXCEPTION block is plpgsql's per-block rollback: `ROLLBACK TO SAVEPOINT` is not legal
-- inside plpgsql (transaction control is not), but raising inside an inner block undoes that block's
-- DATABASE effects while plpgsql VARIABLES keep their values — which is exactly what is needed to measure
-- one ordering, undo it, and measure the other from the same starting state.
do $mr3$
declare
  bal_ab numeric; bal_ba numeric;
  err_ab text := ''; err_ba text := '';
begin
  -- Order A then B (service-role/system path — auth.uid() IS NULL — the branch that MINTS).
  begin
    update public.service_credit_topups set status='verified'
     where id='d1aa1111-0000-4000-8000-000000000001';
    update public.service_credit_topups set status='verified'
     where id='d1aa1111-0000-4000-8000-000000000002';
    select coalesce(sum(amount),0) into bal_ab from public.service_credit_ledger
     where account_id='d1b11111-0000-4000-8000-000000000002' and entry_type='topup';
    raise exception 'MR3_UNDO';          -- undo the writes, keep bal_ab
  exception when others then
    -- Only the marker is expected. A REAL error must be reported, never swallowed into a NULL that
    -- silently reads as a failed relation.
    if sqlerrm not like '%MR3_UNDO%' then err_ab := sqlerrm; end if;
  end;

  -- Order B then A, from the same starting state.
  begin
    update public.service_credit_topups set status='verified'
     where id='d1aa1111-0000-4000-8000-000000000002';
    update public.service_credit_topups set status='verified'
     where id='d1aa1111-0000-4000-8000-000000000001';
    select coalesce(sum(amount),0) into bal_ba from public.service_credit_ledger
     where account_id='d1b11111-0000-4000-8000-000000000002' and entry_type='topup';
    raise exception 'MR3_UNDO';
  exception when others then
    if sqlerrm not like '%MR3_UNDO%' then err_ba := sqlerrm; end if;
  end;

  raise notice 'RESULT mr3_no_unexpected_error=%',
    case when err_ab = '' and err_ba = '' then 'yes'
         else 'NO ' || left(err_ab || err_ba, 70) end;
  raise notice 'RESULT mr3_balance_order_independent=%',
    case when bal_ab is not null and bal_ab = bal_ba then 'yes'
         else 'NO ab=' || coalesce(bal_ab::text,'null') || ' ba=' || coalesce(bal_ba::text,'null') end;
  -- NON-VACUOUS: if neither ordering minted anything, 0 = 0 would "pass" while the mint was broken.
  raise notice 'RESULT mr3_both_orders_minted=%',
    case when coalesce(bal_ab,0) > 0 and coalesce(bal_ba,0) > 0 then 'yes' else 'NO' end;
end
$mr3$;

rollback;
