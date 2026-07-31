-- TB-TRUST-tier-selfmint.sql
--
-- LIVE VULNERABILITY, found 2026-07-31 while modelling the credit economy's abuse surface.
--
-- `recompute_seller_sales_and_tier` derives total_sales (and therefore the bronze/silver/gold ladder) from
-- `marketplace_listings WHERE seller_name = X AND status = 'sold'`. A seller may mark their OWN listing sold
-- — the listing guard permits it deliberately, since withdrawing or closing your own listing is legitimate —
-- and `marketplace_listings` records NO BUYER AT ALL. `marketplace_orders`, which does carry buyer_name, is
-- empty and vestigial since the Stripe removal.
--
-- So the trust ladder the entire marketplace runs on is SELF-MINTABLE, for FREE:
--   12 self-marked listings -> silver.  51 -> gold.  No buyer, no order, no payment, no commission.
--
-- This is strictly worse than the economics predicted. MARKETPLACE_CREDIT_SUSTAINABILITY §8 reasoned that
-- faking a gold badge would cost ~PHP 4,080 in commission on fake jobs — expensive enough to deter casual
-- abuse. It costs ZERO, because total_sales counts a self-declared STATUS rather than a completed
-- TRANSACTION. An economic model is only as good as the event it meters.
--
-- VERIFIED AS A REAL SELLER, not as the table owner: the probe assumes `authenticated` and acts under the
-- seller's own JWT, because postgres bypasses RLS and would have proven nothing
-- ([[feedback_rls_probe_needs_the_role_not_just_claims]]).
--
-- This cell asserts the CURRENT behaviour so the vulnerability is on the board rather than in a document,
-- and it FLIPS to the fixed expectation the moment a fix lands — at which point the expected values below
-- become 0 / bronze.
begin;
set local workhive.row_cap_system_write = 'on';

insert into auth.users(id, email) values ('62000000-0000-4000-8000-00000000000a','tb-tierfarm@gate.local');
insert into public.marketplace_sellers
  (id, worker_name, hive_id, auth_uid, tier, kyb_verified, cert_verified, total_sales, rating_count)
values ('62000000-0000-4000-8000-0000000000f1','TB TierFarm',
        '084c113b-99c0-45c6-a8e8-b4b8349da46d','62000000-0000-4000-8000-00000000000a',
        'bronze', false, false, 0, 0);

insert into public.marketplace_listings(id, seller_name, hive_id, title, section, category, price, status)
select ('62000000-0000-4000-8000-0000000000'||lpad(g::text,2,'0'))::uuid,'TB TierFarm',
       '084c113b-99c0-45c6-a8e8-b4b8349da46d','TB L'||g,'parts','tools',2000,'draft'
from generate_series(1,12) g;

do $probe$
declare n int; v text;
begin
  -- THE SELLER, as themselves, flips their own listings to sold
  perform set_config('request.jwt.claims',
    '{"sub":"62000000-0000-4000-8000-00000000000a","role":"authenticated"}', true);
  set local role authenticated;
  update public.marketplace_listings set status = 'sold' where seller_name = 'TB TierFarm';
  get diagnostics n = row_count;
  raise notice 'RESULT seller_self_marks_sold=%', n;
  reset role;

  select total_sales, tier into n, v from public.marketplace_sellers where worker_name = 'TB TierFarm';
  raise notice 'RESULT tier_from_self_marked=%', v;
  raise notice 'RESULT sales_from_self_marked=%', n;

  -- THE ROOT CAUSE, asserted directly: nothing records who bought.
  raise notice 'RESULT listing_records_buyer=%',
    case when exists (select 1 from information_schema.columns
                       where table_schema='public' and table_name='marketplace_listings'
                         and (column_name ilike '%buyer%' or column_name ilike '%sold_to%'))
         then 'yes' else 'NO' end;

  -- and the table that DOES record a counterparty is unused
  select count(*) into n from public.marketplace_orders;
  raise notice 'RESULT orders_rows=%', n;
end $probe$;

rollback;
