-- =====================================================================
-- J33 · IDLE providers appear as AREA presence (D8), not as nothing and never as a pin
-- =====================================================================
-- D8 states the privacy posture precisely: "live pin only during an active job; idle = AREA
-- presence". Half of that shipped - the geo gate proves an idle provider's exact position is
-- unreadable by anyone. The OTHER half was never built: a client saw NOTHING, so a hail went out
-- with no idea whether anybody was even online. That is both a broken promise and the classic
-- thin-marketplace failure (you cannot tell an empty market from a broken one).
--
-- This view is deliberately COARSE and coordinate-free:
--   * groups by the declared service AREA (a city/region string), never a point;
--   * exposes only a COUNT and the categories covered - no ids, no names, no geography column,
--     so it cannot be joined back to an individual provider's position;
--   * counts only `online` providers (on_job providers are busy; offline are absent).
-- A count is a liquidity signal. A pin is surveillance. This is the first, not the second.

BEGIN;

drop view if exists public.v_service_area_presence;
-- NOTE: two unnest()s in one SELECT list ZIP (padded with NULLs) rather than cross-joining - the
-- first cut of this view produced a phantom blank-area bucket and inflated counts. LATERAL makes
-- the expansion explicit, and count(DISTINCT sp.id) means a provider covering 3 categories in one
-- city is still ONE provider online there.
create view public.v_service_area_presence
with (security_invoker = false) as
select
  a.area                                                   as service_area,
  count(distinct sp.id)::int                               as providers_online,
  array_agg(distinct c.cat order by c.cat)                 as categories,
  count(distinct sp.id) filter (where sp.verified)::int    as verified_online,
  -- canonical truth-view signal-trust contract
  1                                                        as _source_count,
  max(sp.updated_at)                                       as _freshness_ts,
  'service_area_presence:v2'                               as _canonical_version
from public.service_providers sp
cross join lateral unnest(sp.service_areas) as a(area)
cross join lateral unnest(sp.categories)    as c(cat)
where sp.availability = 'online'
  and coalesce(a.area, '') <> ''
group by a.area;

comment on view public.v_service_area_presence is
  'J33/D8: coarse, coordinate-free liquidity signal - how many ONLINE providers cover each declared service area, and which categories. Deliberately exposes no id, name, or geography, so idle presence can never be resolved to a person or a point (the live pin stays exclusive to v_service_job_tracking during an active job).';

grant select on public.v_service_area_presence to anon, authenticated;

insert into public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values
  ('service_area_presence', 'view', 'v_service_area_presence', 'marketplace', 'realtime',
   '{"privacy": "D8 - area-level counts only; no id/name/geography column exists on this view", "counts": "availability = online"}'::jsonb,
   'Coarse idle-provider presence by declared service area: the liquidity signal a client needs before hailing, without exposing anybody''s position.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind = excluded.source_kind, source_name = excluded.source_name,
      owner_skill = excluded.owner_skill, freshness = excluded.freshness,
      contract = excluded.contract, description = excluded.description;

COMMIT;
