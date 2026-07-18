-- ============================================================================
-- C8 — Marketplace Row-Level Security  (deep-walk finding, 2026-07-06)
-- ============================================================================
-- FINDING: all marketplace tables shipped with RLS DISABLED (relrowsecurity=f,
-- 0 policies) while the rest of the platform enforces it. Impact: any
-- authenticated user could read/mutate ANY seller's/buyer's rows (cross-seller
-- IDOR — cf. marketplace-seller close-inquiry id-only write), seller PII/certs
-- + escrow orders/disputes were world-read/writable, AND marketplace_platform_admins
-- was writable by anyone (self-grant admin = privilege escalation).
--
-- MODEL (Ian: "public marketplace"): listings + seller profiles are publicly
-- browsable (cross-hive, incl. signed-out for PUBLISHED listings); everything
-- else is owner/party-scoped; platform admins (marketplace_platform_admins) may
-- moderate. Admin runs via the anon key + a user session (NOT service-role), so
-- an explicit admin-allow branch is required in each policy.
--
-- IDENTITY MAPPING: the tables key parties by worker_name (display string), not
-- auth_uid. auth_worker_names() maps auth.uid() -> the caller's worker_name(s)
-- via hive_members (general) UNION marketplace_sellers (seller). This is why the
-- 2026-07-06 auth_uid backfill on marketplace_sellers matters. NOTE: security is
-- as strong as worker_name uniqueness (a pre-existing data-model assumption).
--
-- Idempotent. LOCAL-applied for test; prod deploy is Ian's gate.
-- ============================================================================

-- ---- helper functions (security definer so they can read the map tables) ----
create or replace function public.auth_worker_names()
  returns setof text
  language sql stable security definer set search_path = public as $$
  select worker_name from public.hive_members
    where auth_uid = auth.uid() and status = 'active'
  union
  select worker_name from public.marketplace_sellers
    where auth_uid = auth.uid();
$$;

create or replace function public.is_marketplace_admin()
  returns boolean
  language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.marketplace_platform_admins pa
    where pa.worker_name in (select public.auth_worker_names())
  );
$$;

grant execute on function public.auth_worker_names() to anon, authenticated;
grant execute on function public.is_marketplace_admin() to anon, authenticated;

-- ---- best-effort backfill: link existing seller rows to their auth identity --
-- (so a seller who is not an active hive_member still resolves post-RLS)
update public.marketplace_sellers s
   set auth_uid = hm.auth_uid
  from public.hive_members hm
 where s.auth_uid is null
   and hm.worker_name = s.worker_name
   and hm.auth_uid is not null;

-- ============================ marketplace_sellers ===========================
alter table public.marketplace_sellers enable row level security;
drop policy if exists mkt_sellers_read   on public.marketplace_sellers;
drop policy if exists mkt_sellers_insert on public.marketplace_sellers;
drop policy if exists mkt_sellers_update on public.marketplace_sellers;
drop policy if exists mkt_sellers_delete on public.marketplace_sellers;
-- seller profiles are visible to any SIGNED-IN user (buyers browse storefronts), but NOT to anon —
-- avoids anon scraping of auth_uid/messenger_username/certs, and keeps the policy non-always-true so it
-- doesn't defeat the write policies (validate_rls_no_permissive_bypass). Listings stay anon-public via
-- their status='published' branch, so signed-out catalogue browsing still works.
create policy mkt_sellers_read   on public.marketplace_sellers for select using (auth.uid() is not null);
create policy mkt_sellers_insert on public.marketplace_sellers for insert with check (auth_uid = auth.uid());
create policy mkt_sellers_update on public.marketplace_sellers for update
  using (auth_uid = auth.uid() or public.is_marketplace_admin())
  with check (auth_uid = auth.uid() or public.is_marketplace_admin());
create policy mkt_sellers_delete on public.marketplace_sellers for delete
  using (auth_uid = auth.uid() or public.is_marketplace_admin());

-- ============================ marketplace_listings ==========================
alter table public.marketplace_listings enable row level security;
drop policy if exists mkt_listings_read   on public.marketplace_listings;
drop policy if exists mkt_listings_insert on public.marketplace_listings;
drop policy if exists mkt_listings_update on public.marketplace_listings;
drop policy if exists mkt_listings_delete on public.marketplace_listings;
create policy mkt_listings_read on public.marketplace_listings for select
  using (status = 'published'
      or seller_name in (select public.auth_worker_names())
      or public.is_marketplace_admin());
create policy mkt_listings_insert on public.marketplace_listings for insert
  with check (seller_name in (select public.auth_worker_names()));
create policy mkt_listings_update on public.marketplace_listings for update
  using (seller_name in (select public.auth_worker_names()) or public.is_marketplace_admin())
  with check (seller_name in (select public.auth_worker_names()) or public.is_marketplace_admin());
create policy mkt_listings_delete on public.marketplace_listings for delete
  using (seller_name in (select public.auth_worker_names()) or public.is_marketplace_admin());

-- ============================ marketplace_orders ============================
alter table public.marketplace_orders enable row level security;
drop policy if exists mkt_orders_read   on public.marketplace_orders;
drop policy if exists mkt_orders_insert on public.marketplace_orders;
drop policy if exists mkt_orders_update on public.marketplace_orders;
drop policy if exists mkt_orders_delete on public.marketplace_orders;
create policy mkt_orders_read on public.marketplace_orders for select
  using (buyer_name in (select public.auth_worker_names())
      or seller_name in (select public.auth_worker_names())
      or public.is_marketplace_admin());
create policy mkt_orders_insert on public.marketplace_orders for insert
  with check (buyer_name in (select public.auth_worker_names()));
create policy mkt_orders_update on public.marketplace_orders for update
  using (buyer_name in (select public.auth_worker_names())
      or seller_name in (select public.auth_worker_names())
      or public.is_marketplace_admin())
  with check (buyer_name in (select public.auth_worker_names())
      or seller_name in (select public.auth_worker_names())
      or public.is_marketplace_admin());
create policy mkt_orders_delete on public.marketplace_orders for delete
  using (public.is_marketplace_admin());

-- =========================== marketplace_inquiries ==========================
alter table public.marketplace_inquiries enable row level security;
drop policy if exists mkt_inq_read   on public.marketplace_inquiries;
drop policy if exists mkt_inq_insert on public.marketplace_inquiries;
drop policy if exists mkt_inq_update on public.marketplace_inquiries;
drop policy if exists mkt_inq_delete on public.marketplace_inquiries;
create policy mkt_inq_read on public.marketplace_inquiries for select
  using (buyer_name in (select public.auth_worker_names())
      or seller_name in (select public.auth_worker_names())
      or public.is_marketplace_admin());
create policy mkt_inq_insert on public.marketplace_inquiries for insert
  with check (buyer_name in (select public.auth_worker_names()));
create policy mkt_inq_update on public.marketplace_inquiries for update
  using (buyer_name in (select public.auth_worker_names())
      or seller_name in (select public.auth_worker_names())
      or public.is_marketplace_admin())
  with check (buyer_name in (select public.auth_worker_names())
      or seller_name in (select public.auth_worker_names())
      or public.is_marketplace_admin());
create policy mkt_inq_delete on public.marketplace_inquiries for delete
  using (public.is_marketplace_admin());

-- =========================== marketplace_disputes ===========================
alter table public.marketplace_disputes enable row level security;
drop policy if exists mkt_disp_read   on public.marketplace_disputes;
drop policy if exists mkt_disp_insert on public.marketplace_disputes;
drop policy if exists mkt_disp_update on public.marketplace_disputes;
drop policy if exists mkt_disp_delete on public.marketplace_disputes;
create policy mkt_disp_read on public.marketplace_disputes for select
  using (opened_by in (select public.auth_worker_names())
      or seller_name in (select public.auth_worker_names())
      or public.is_marketplace_admin());
create policy mkt_disp_insert on public.marketplace_disputes for insert
  with check (opened_by in (select public.auth_worker_names()));
create policy mkt_disp_update on public.marketplace_disputes for update
  using (opened_by in (select public.auth_worker_names())
      or seller_name in (select public.auth_worker_names())
      or public.is_marketplace_admin())
  with check (opened_by in (select public.auth_worker_names())
      or seller_name in (select public.auth_worker_names())
      or public.is_marketplace_admin());
create policy mkt_disp_delete on public.marketplace_disputes for delete
  using (public.is_marketplace_admin());

-- ====================== marketplace_platform_admins =========================
-- Read: any authed user (the admin gate + is_marketplace_admin() read it).
-- Write: existing admins ONLY (prevents self-grant escalation). The FIRST admin
-- is seeded by migration/service-role (which bypasses RLS), never by a client.
alter table public.marketplace_platform_admins enable row level security;
drop policy if exists mkt_admins_read  on public.marketplace_platform_admins;
drop policy if exists mkt_admins_write on public.marketplace_platform_admins;
create policy mkt_admins_read  on public.marketplace_platform_admins for select
  using (auth.uid() is not null);
create policy mkt_admins_write on public.marketplace_platform_admins for all
  using (public.is_marketplace_admin())
  with check (public.is_marketplace_admin());
