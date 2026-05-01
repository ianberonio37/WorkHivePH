-- WorkHive Marketplace Tables
-- Run after 20260501000002_skill_profiles_auth_uid.sql

-- =============================================
-- marketplace_listings
-- =============================================
create table if not exists public.marketplace_listings (
  id               uuid        primary key default gen_random_uuid(),
  hive_id          uuid        references public.hives(id) on delete set null,
  seller_name      text        not null,
  seller_contact   text,
  seller_verified  boolean     not null default false,
  completed_sales  integer     not null default 0,
  rating_avg       numeric(3,2),
  section          text        not null check (section in ('parts','training','jobs')),
  category         text,
  title            text        not null,
  description      text,
  price            numeric(14,2),
  condition        text        check (condition in ('new','used','refurb')),
  location         text,
  image_url        text,
  status           text        not null default 'draft'
                               check (status in ('draft','published','sold','removed')),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index if not exists marketplace_listings_section_status
  on public.marketplace_listings (section, status);

create index if not exists marketplace_listings_hive_id
  on public.marketplace_listings (hive_id);

-- =============================================
-- marketplace_inquiries
-- =============================================
create table if not exists public.marketplace_inquiries (
  id             uuid        primary key default gen_random_uuid(),
  listing_id     uuid        references public.marketplace_listings(id) on delete cascade,
  hive_id        uuid        references public.hives(id) on delete set null,
  buyer_name     text        not null,
  buyer_contact  text,
  message        text        not null,
  status         text        not null default 'pending'
                             check (status in ('pending','replied','closed')),
  created_at     timestamptz not null default now()
);

create index if not exists marketplace_inquiries_listing_id
  on public.marketplace_inquiries (listing_id);

-- =============================================
-- marketplace_reviews
-- =============================================
create table if not exists public.marketplace_reviews (
  id                uuid        primary key default gen_random_uuid(),
  listing_id        uuid        references public.marketplace_listings(id) on delete cascade,
  reviewer_name     text        not null,
  rating            integer     not null check (rating between 1 and 5),
  comment           text,
  verified_purchase boolean     not null default false,
  created_at        timestamptz not null default now()
);

create index if not exists marketplace_reviews_listing_id
  on public.marketplace_reviews (listing_id);

-- =============================================
-- Grants (required for RLS-ready tables —
-- Supabase dashboard auto-grants; migrations do not)
-- =============================================
grant select, insert on public.marketplace_listings   to anon, authenticated;
grant update (status, updated_at) on public.marketplace_listings to authenticated;

grant select, insert on public.marketplace_inquiries  to anon, authenticated;

grant select on public.marketplace_reviews            to anon, authenticated;
grant insert on public.marketplace_reviews            to authenticated;
