-- A stranger reads listings through a view that does not carry the seller's contact (EX-HP H2, 2026-09-07).
--
-- Measured anonymously through PostgREST: SELECT * on marketplace_listings returned published rows with
-- seller_contact filled in, plus moderation_reason / moderated_by. The marketplace page never shows a
-- contact - "Contact Seller" opens an INQUIRY, which is the whole design - so the exposure was not on
-- any page a person sees; it was the raw table, harvestable by a scraper at one request per page of 26
-- columns. The read policy is PUBLIC on published rows and anon held a table-level SELECT.
--
-- WHY A SECOND VIEW RATHER THAN A COLUMN GRANT. v_marketplace_listings_truth runs as the caller
-- (security_invoker) and names seller_contact, so restricting that column for anon on the base table
-- would break the very view the marketplace reads twelve times - this platform has already broken a
-- feed that way once. And masking the column inside an invoker view does not help: Postgres checks
-- column privilege on every column a query REFERENCES, taken branch or not. So:
--
--   * v_marketplace_listings_public  - runs as its owner (NOT security_invoker), which is why it carries
--     its own row filter: published rows, or the caller's own listings by auth_worker_names(). It omits
--     seller_contact and every moderation_* column. Every column it does carry keeps the truth view's
--     name, so the page's twelve reads move with a one-word change.
--   * anon loses SELECT on the base table. Signed-in users keep it, so the truth view still serves the
--     seller dashboard and the admin surface, which are the only readers of the contact.
create or replace view public.v_marketplace_listings_public as
select l.id, l.hive_id, l.seller_name,
       coalesce(ms.kyb_verified, false) or coalesce(ms.cert_verified, false) as seller_verified,
       coalesce(ms.total_sales, 0) as completed_sales,
       ms.rating_avg,
       l.section, l.category, l.title, l.description, l.price, l.condition, l.location, l.image_url,
       l.status, l.view_count, l.created_at, l.updated_at,
       ms.tier as seller_tier, ms.kyb_verified as seller_kyb_verified, ms.total_sales as seller_total_sales,
       ms.rating_avg as seller_rating_avg_live, ms.rating_count as seller_rating_count,
       ms.response_rate as seller_response_rate, ms.response_time_h as seller_response_time_h,
       l.status = 'published' as is_published, l.status = 'sold' as is_sold, l.status = 'draft' as is_draft,
       l.part_number
  from public.marketplace_listings l
  left join public.marketplace_sellers ms on ms.worker_name = l.seller_name
 where l.status = 'published'
    or l.seller_name in (select public.auth_worker_names());

grant select on public.v_marketplace_listings_public to anon, authenticated;
revoke select on public.marketplace_listings from anon;

-- ★THE SCHEMA'S DEFAULT PRIVILEGES GRANTED THE VIEW ALL, AND A DEFINER VIEW IS AUTO-UPDATABLE. Applying
-- the block above left anon holding INSERT, UPDATE and DELETE on v_marketplace_listings_public - a view
-- that runs as its owner - which is a write path into marketplace_listings that skips RLS entirely. A
-- read-only view must SAY it is read-only, because the defaults will not. SELECT alone survives.
revoke insert, update, delete, references, trigger, truncate on public.v_marketplace_listings_public from anon, authenticated;

-- The engine anchor (validate_canonical_anchor L2): every view a page reads is registered where the
-- platform keeps its canonical sources, or the gate counts it as an un-anchored engine object.
insert into public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values ('marketplace', 'view', 'v_marketplace_listings_public', 'marketplace', 'on_demand',
        '{"boundary": "published listings, or the caller''s own; no seller_contact, no moderation_*; read-only (definer view with its own WHERE)"}'::jsonb,
        'Public listings view - the marketplace and seller-profile read path for anonymous and signed-in browsing. The truth view keeps the contact for the seller dashboard and admin.')
on conflict do nothing;
