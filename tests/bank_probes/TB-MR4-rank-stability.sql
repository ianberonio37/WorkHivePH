-- TB-MR4-rank-stability.sql
--
-- METAMORPHIC RELATION 4 · RANK STABILITY: the same query over an unchanged corpus must return the same ORDER.
-- No expected value exists for "what order should the marketplace be in" — only a relation BETWEEN two runs —
-- which is exactly why this surface had no oracle before (the bank was 233/300 `refusal`).
--
-- THE DEFECT THIS FOUND (real, proven, then fixed 2026-07-31). marketplace.html browsed with
--   .order('created_at', {ascending:false}).limit(PAGE_SIZE)
-- and `created_at` alone is NOT a total order. A bulk import inserts many listings inside ONE transaction,
-- where now() is FIXED, so every row shares an identical timestamp. Postgres promises nothing about the order
-- of tied rows and it genuinely moves: touching an UNRELATED column on one tied row (an ordinary edit — MVCC
-- writes a new tuple at the end of the heap) made 4 of 12 rows come back at a DIFFERENT RANK while the row SET
-- was identical. Under `.limit(PAGE_SIZE)` that is a user-visible bug: a listing can be shown twice across a
-- refresh, or skipped entirely between pages. Fixed by making the order TOTAL with the unique `id` as a
-- tiebreaker, at all six paginated sites in marketplace.html.
--
-- WHY THE NON-VACUITY CHECK IS LOAD-BEARING ([[feedback_a_metamorphic_relation_needs_a_non_vacuity_check]]).
-- "The order was the same twice" is trivially true whenever no two rows tie, and today's seeded corpus has
-- ZERO ties (21 published listings, 21 distinct timestamps) — so a naive version of this test would have
-- passed forever while the defect sat there. The probe therefore INDUCES the tie (a realistic 6-row bulk
-- import in one transaction) and then asserts BOTH directions:
--   * the product's order (with the id tiebreaker) is STABLE, and
--   * the same query WITHOUT the tiebreaker is genuinely UNSTABLE.
-- The second assertion is what proves the first is doing work. If it ever flips to NO, the fixture stopped
-- creating ties and this cell has gone vacuous — that is a red, not a pass.
begin;

-- a realistic BULK IMPORT: one transaction => one now() => six listings sharing an identical created_at
insert into public.marketplace_listings(id, seller_name, title, description, section, category, price, location, status)
select ('b1000000-0000-4000-8000-0000000000'||lpad(g::text,2,'0'))::uuid,
       'MR4 Seller','MR4 Listing '||g,'desc '||g,'parts','tools',100+g,'Baguio','published'
from generate_series(1,6) g;

do $probe$
declare
  fixed_a uuid[]; fixed_b uuid[];
  loose_a uuid[]; loose_b uuid[];
  tie_surplus int; missing int;
begin
  -- NON-VACUITY (1): the corpus really does contain tied sort keys, so "same order twice" is not free
  select count(*) - count(distinct created_at) into tie_surplus
    from public.v_marketplace_listings_truth where status='published' and section='parts';
  raise notice 'RESULT mr4_ties_exist=%', case when tie_surplus > 0 then 'yes' else 'NO' end;

  -- the PRODUCT's query shape (total order: created_at desc, id desc) and the OLD one (created_at only)
  loose_a := array(select id from public.v_marketplace_listings_truth
                   where status='published' and section='parts' order by created_at desc limit 12);
  fixed_a := array(select id from public.v_marketplace_listings_truth
                   where status='published' and section='parts' order by created_at desc, id desc limit 12);

  -- the METAMORPHIC TRANSFORM: an edit that touches NEITHER the sort key nor the row set. The result order
  -- must be invariant under it. (This is an ordinary listing edit — the most common write on the table.)
  update public.marketplace_listings set description = 'touched'
   where id = 'b1000000-0000-4000-8000-000000000003';

  loose_b := array(select id from public.v_marketplace_listings_truth
                   where status='published' and section='parts' order by created_at desc limit 12);
  fixed_b := array(select id from public.v_marketplace_listings_truth
                   where status='published' and section='parts' order by created_at desc, id desc limit 12);

  -- THE RELATION: same query, same corpus, same order.
  raise notice 'RESULT mr4_rank_stable=%', case when fixed_a = fixed_b then 'yes' else 'NO' end;

  -- The corpus must be unchanged, so a difference above would be a RANK change and not a row-set change.
  -- (Without this, a query that silently dropped a row would "pass" the stability check by shrinking.)
  select count(*) into missing from (
    select unnest(fixed_a) except select unnest(fixed_b)
    union all
    select unnest(fixed_b) except select unnest(fixed_a)) d;
  raise notice 'RESULT mr4_row_set_unchanged=%', case when missing = 0 then 'yes' else 'NO' end;

  -- NON-VACUITY (2): the UNTIED query really is unstable under the same transform. This is the teeth check —
  -- it proves the tiebreaker is what buys stability, rather than the test asserting a tautology.
  raise notice 'RESULT mr4_untied_order_is_unstable=%', case when loose_a <> loose_b then 'yes' else 'NO' end;
end $probe$;

rollback;
