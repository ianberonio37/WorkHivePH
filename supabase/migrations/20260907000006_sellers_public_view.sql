-- A stranger reads a seller through a view that carries the badge and not the contact (EX-HP H2, 2026-09-07).
--
-- 20260803000027 made a seller row anon-readable on purpose (a trust badge only signed-in people can see
-- does not do its job) and narrowed anon to the ten badge columns with a COLUMN grant. But the page a
-- stranger actually opens - marketplace-seller-profile.html, and the seller card on marketplace.html -
-- reads v_marketplace_sellers_truth, which runs as the caller (security_invoker) and names
-- messenger_username, certifications, created_at, kyb_verified_at and id. Postgres checks column
-- privilege on every column a query REFERENCES, so for anon the whole read raised
--     permission denied for table marketplace_sellers
-- and the profile of a seller who is offering something publicly was dark to exactly the visitor the
-- badge exists to persuade. Surfaced 2026-09-07 while proving 20260907000005 through the psql recipe.
--
-- Same shape as v_marketplace_listings_public: a view that runs as its OWNER, carries its own row filter
-- (the anon policy's predicate, or a signed-in caller), keeps every column name the truth view uses so
-- the page reads move with a one-word change, and MASKS the signed-in-only columns for a stranger instead
-- of omitting them - the seller card still shows "Message on Messenger" to a signed-in buyer, and a
-- stranger gets NULL there, which the page already renders as "sign in to contact".
create or replace view public.v_marketplace_sellers_public as
select s.worker_name, s.hive_id, s.tier, s.kyb_verified, s.cert_verified,
       s.total_sales, s.rating_avg, s.rating_count, s.response_rate, s.response_time_h,
       coalesce(active_listings.n, 0::bigint) as active_listings_count,
       coalesce(total_orders.n, 0::bigint)    as total_orders_count,
       active_listings.last_at                as last_listed_at,
       total_orders.last_at                   as last_order_at,
       (s.kyb_verified and s.cert_verified)   as is_verified_public,
       (s.messenger_username is not null and s.certifications is not null) as profile_complete,
       -- signed-in-only: the same columns 20260803000027 kept from anon, masked rather than referenced
       case when auth.uid() is not null then s.messenger_username end as messenger_username,
       case when auth.uid() is not null then s.certifications    end as certifications,
       case when auth.uid() is not null then s.kyb_verified_at   end as kyb_verified_at,
       case when auth.uid() is not null then s.cert_verified_at  end as cert_verified_at,
       case when auth.uid() is not null then s.created_at        end as created_at
  from public.marketplace_sellers s
  left join lateral (select count(*) as n, max(l.created_at) as last_at
                       from public.marketplace_listings l
                      where l.seller_name = s.worker_name and l.status = 'published') active_listings on true
  left join lateral (select count(*) as n, max(o.created_at) as last_at
                       from public.marketplace_orders o
                      where o.seller_name = s.worker_name) total_orders on true
 where auth.uid() is not null
    or public.seller_has_published_listing(s.worker_name);

grant select on public.v_marketplace_sellers_public to anon, authenticated;
-- a definer view is auto-updatable and the schema's default privileges grant it ALL: say read-only (H2 lesson)
revoke insert, update, delete, references, trigger, truncate on public.v_marketplace_sellers_public from anon, authenticated;

insert into public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, contract, description)
-- canonical_sources is keyed by domain (PRIMARY KEY (domain)); a view registers under its own name, the way
-- marketplace_sellers_truth and marketplace_listings_truth do - 'marketplace' is already the listings view's key.
values ('marketplace_sellers_public', 'view', 'v_marketplace_sellers_public', 'marketplace', 'on_demand',
        '{"boundary": "sellers with a published listing, or every seller for a signed-in caller; badge columns for everyone, messenger_username / certifications / timestamps NULL for anon; read-only (definer view with its own WHERE)"}'::jsonb,
        'Public seller view - the seller-profile page and the marketplace seller card read path for anonymous and signed-in browsing. The truth view keeps the full row for the seller dashboard.')
on conflict do nothing;
