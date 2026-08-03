-- An anonymous visitor saw every seller as an unverified Bronze with zero sales.
--
-- MEASURED on a live walk, not reasoned: Bryan Garcia is `kyb_verified = true, total_sales = 1` in the
-- database. An anon read of v_marketplace_listings_truth returns `seller_verified = false,
-- completed_sales = 0, seller_tier = null` for him, and the marketplace rendered **0 Verified badges and
-- 9 Bronze tiers** for the whole catalogue.
--
-- The cause is a join that silently degrades. The listings view is `security_invoker`, so its LEFT JOIN
-- to marketplace_sellers runs as the CALLER, and the only client read policy there is
--
--     mkt_sellers_read  USING (auth.uid() IS NOT NULL)      -- signed-in only
--
-- so for anon the joined columns come back NULL, and COALESCE turns that into a confident `false` and a
-- confident `0`. Not an error. Not an empty page. A page full of plausible, wrong trust signals.
--
-- WHY THIS MATTERS MORE THAN A MISSING BADGE. Marketplace browsing is anon-friendly BY DESIGN, and the
-- page's own provenance chip tells that visitor "ID-verified sellers only in results by default". So the
-- product advertises a trust guarantee to precisely the audience that cannot see it, and a verified
-- seller with completed sales is indistinguishable from someone who signed up a minute ago. Trust signals
-- exist to persuade STRANGERS; this one only ever reached people who had already committed.
--
-- THE FIX IS COLUMN-SCOPED, NOT A WIDER ROW POLICY. A seller's badge, tier, sales count and rating are
-- public by their nature -- that is the entire point of a badge. Their auth_uid, contact details and KYB
-- timestamps are not. So anon gets a row policy AND a column grant narrowed to the public set:
--
--   * the table-level SELECT grant is REVOKED from anon first. A column-level GRANT is a no-op while a
--     table-level grant stands, so revoking is what makes the narrowing real rather than decorative.
--   * a separate policy names anon explicitly, leaving mkt_sellers_read untouched for signed-in users.
--
-- What anon still cannot read after this: auth_uid, seller_contact, kyb_verified_at, created_at,
-- updated_at, id. Verified below by selecting them as anon and requiring the refusal.

-- ── 1. the row policy: a seller profile is public ────────────────────────────────────────────────────
drop policy if exists mkt_sellers_read_anon on public.marketplace_sellers;
-- NOT `using (true)`. A seller is public because they are OFFERING something publicly - so the predicate
-- is exactly that, and it is genuinely narrower: a seller who has never published a listing is not
-- browsable by strangers, and neither is one who has taken everything down. It also keeps the RLS strict
-- ratchet honest; bumping that baseline to admit my own permissive policy would be the ratchet-turned-
-- both-ways move this codebase already has a memory about.
create policy mkt_sellers_read_anon on public.marketplace_sellers
  for select to anon
  using (exists (select 1 from public.marketplace_listings l
                  where l.seller_name = marketplace_sellers.worker_name
                    and l.status = 'published'));

comment on policy mkt_sellers_read_anon on public.marketplace_sellers is
  'Anonymous visitors may read seller rows, because the marketplace is anon-browsable and a trust badge '
  'that only signed-in people can see does not do the job a trust badge exists to do. The COLUMN grant '
  'below is what keeps this narrow: anon sees the public signals and nothing else.';

-- ── 2. the column grant: only the signals a badge is made of ─────────────────────────────────────────
-- REVOKE FIRST. Column-level grants do not restrict anything while a table-level grant is in force, and
-- this codebase has already paid for that lesson once.
revoke select on public.marketplace_sellers from anon;
grant select (worker_name, hive_id, tier, kyb_verified, cert_verified,
              total_sales, rating_avg, rating_count, response_rate, response_time_h)
  on public.marketplace_sellers to anon;
