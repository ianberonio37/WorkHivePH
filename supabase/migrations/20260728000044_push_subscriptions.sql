-- ─────────────────────────────────────────────────────────────────────────────
-- push_subscriptions (SERVICE_HAILING P5 / G3): Web Push endpoints so a provider
-- receives job offers with the tab CLOSED - without this, hailing fails on mobile
-- (the G3 gap analysis). One row per browser endpoint, owner-scoped RLS; sends go
-- through the notify-push edge fn (service-role) which prunes dead endpoints on
-- delivery failure (the harvested web-push recipe, substrate external-service-
-- hailing-web-push-vapid).
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.push_subscriptions (
  id         uuid primary key default gen_random_uuid(),
  auth_uid   uuid not null references auth.users(id) on delete cascade,
  endpoint   text not null unique,
  p256dh     text not null,
  auth       text not null,
  user_agent text,
  created_at timestamptz not null default now(),
  last_ok_at timestamptz
);
comment on table public.push_subscriptions is
  'Web Push endpoints (VAPID). Owner-scoped; the notify-push edge fn (service-role) sends and prunes dead endpoints.';

create index if not exists push_subscriptions_auth_uid on public.push_subscriptions (auth_uid);

alter table public.push_subscriptions enable row level security;

revoke all on public.push_subscriptions from anon, authenticated;
grant select, insert, update, delete on public.push_subscriptions to authenticated;

drop policy if exists push_subscriptions_own on public.push_subscriptions;
create policy push_subscriptions_own on public.push_subscriptions
  for all to authenticated
  using (auth_uid = auth.uid()) with check (auth_uid = auth.uid());

insert into public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values ('service_hailing', 'table', 'push_subscriptions', 'notifications', 'realtime',
        '{"key": ["endpoint"], "writes": "owner-scoped client upsert; sends+pruning via notify-push (service-role)"}'::jsonb,
        'Web Push endpoints for job-offer delivery with the tab closed (G3).')
on conflict do nothing;
