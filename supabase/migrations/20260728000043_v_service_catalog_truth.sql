-- ─────────────────────────────────────────────────────────────────────────────
-- v_service_catalog_truth — the Engine wrapper for the rate card (P4 follow-through).
-- The kpi-canonical gate caught marketplace.html + marketplace-seller.html reading
-- service_catalog RAW — the arc's own §1 rule is "Dashboard reads Engine views,
-- never Fuel", and with 2+ surfaces reading it the gate's own guidance says build
-- the truth wrapper. Carries the canonical signal-trust meta columns.
-- ─────────────────────────────────────────────────────────────────────────────
create or replace view public.v_service_catalog_truth
with (security_invoker = false) as
select
  c.id, c.segment, c.category, c.name, c.description, c.unit, c.base_rate, c.active,
  c.created_at, c.updated_at,
  1 as _source_count,
  c.updated_at as _freshness_ts,
  'service_catalog_truth:v1' as _canonical_version
from public.service_catalog c
where c.active = true;
comment on view public.v_service_catalog_truth is
  'Rate-card truth (active rows only) — the ONLY Dashboard read path for service_catalog.';
grant select on public.v_service_catalog_truth to anon, authenticated;

insert into public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values ('service_hailing', 'view', 'v_service_catalog_truth', 'marketplace', 'on_demand',
        '{"boundary": "active catalog rows; public browse (P8 consumer door)"}'::jsonb,
        'Rate-card truth view — Dashboard/Brain read path for service_catalog.')
on conflict do nothing;
