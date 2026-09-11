-- A stranger can read a seller again (EX-HP H2 follow-up, 2026-09-07).
--
-- 20260907000004 revoked anon's SELECT on marketplace_listings so a scraper cannot harvest seller_contact
-- from the raw table. The anon read policy on marketplace_sellers, mkt_sellers_read_anon, decides who is
-- visible with a subquery on that same table:
--     EXISTS (SELECT 1 FROM marketplace_listings l WHERE l.seller_name = worker_name AND l.status = 'published')
-- A policy predicate runs with the CALLER's privileges, so for anon it now raised
--     permission denied for table marketplace_listings
-- and every anonymous read of marketplace_sellers - and of v_marketplace_sellers_truth, which runs as the
-- caller - failed with it: the public seller-profile page and the marketplace's seller cards were dark
-- for a logged-out visitor. Caught by the psql recipe index__anon_zero_rows (allowlist_still_public 3 -> 1).
--
-- The predicate keeps its meaning and stops depending on anon's table privileges: a SECURITY DEFINER
-- helper answers "does this seller have a published listing" as the owner. It returns ONE boolean about
-- ONE seller name and exposes no listing column, so it widens nothing the base-table revoke closed.
create or replace function public.seller_has_published_listing(p_seller_name text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.marketplace_listings l
     where l.seller_name = p_seller_name and l.status = 'published'
  );
$$;
revoke all on function public.seller_has_published_listing(text) from public;
grant execute on function public.seller_has_published_listing(text) to anon, authenticated;

alter policy mkt_sellers_read_anon on public.marketplace_sellers
  using (public.seller_has_published_listing(worker_name));
