-- =====================================================================
-- J26 · SHOWCASE (consented completion stories)  +  J25 · LIQUIDITY (top-provider leaderboard)
-- =====================================================================
-- The last two §1c booster engines that shipped as CTAs only:
--   * public-feed.html was promised as "Showcase + SEO acquisition: consented job-completion
--     stories, provider highlights" - but no completion story was ever published, so the
--     acquisition surface had nothing to acquire WITH.
--   * community.html was promised as the "Liquidity engine: provider Q&A, recommendation threads,
--     top-provider leaderboard" - only a bridge card shipped.
--
-- CONSENT IS THE WHOLE DESIGN of the showcase half. A completed job is private commercial
-- information: who hired whom, for what, at what address. So publication is:
--   * OPT-IN per job (the client ticks it; default is silence),
--   * authored by an RPC, never a client INSERT, so the published text is composed server-side
--     from a fixed template and cannot be turned into a free-text broadcast channel,
--   * ADDRESS-FREE and CLIENT-ANONYMOUS by construction - the story names the provider, the trade
--     and the city, never the client or the site.
--
-- The leaderboard half is a VIEW over already-guarded truth (completions + VIEW-computed rating),
-- so it invents no new trust signal and nothing on it can be forged.

BEGIN;

-- ── J26: consent flag + the publisher ───────────────────────────────────────────────
alter table public.service_requests
  add column if not exists showcase_consent boolean not null default false,
  add column if not exists showcase_post_id uuid;

comment on column public.service_requests.showcase_consent is
  'J26: the CLIENT opted this completed job into the public showcase. Default false - silence unless asked.';

create or replace function public.publish_service_showcase(p_request_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_req  public.service_requests%rowtype;
  v_prov public.service_providers%rowtype;
  v_cat  text;
  v_city text;
  v_id   uuid;
begin
  select r.* into v_req from public.service_requests r where r.id = p_request_id;
  if v_req.id is null then
    return jsonb_build_object('published', false, 'reason', 'not_found');
  end if;
  -- only the CLIENT of the job may publish it, and only once it is genuinely finished
  if v_req.client_auth_uid <> auth.uid() then
    return jsonb_build_object('published', false, 'reason', 'not_your_job');
  end if;
  if v_req.status not in ('completed', 'settled') then
    return jsonb_build_object('published', false, 'reason', 'job_not_finished');
  end if;
  if v_req.showcase_post_id is not null then
    return jsonb_build_object('published', false, 'reason', 'already_published');
  end if;

  select sp.* into v_prov from public.service_providers sp where sp.id = v_req.matched_provider_id;
  if v_prov.id is null then
    return jsonb_build_object('published', false, 'reason', 'no_provider');
  end if;

  select c.category into v_cat from public.service_catalog c where c.id = v_req.catalog_item_id;
  v_cat  := coalesce(v_cat, 'Service');
  -- city only, never the street address the client typed
  v_city := coalesce((v_prov.service_areas)[1], 'the area');

  insert into public.community_posts (hive_id, author_name, content, category, public, auth_uid)
  values (
    coalesce(v_req.hive_id, (select id from public.hives order by created_at limit 1)),
    v_prov.display_name,
    v_cat || ' job completed in ' || v_city || ' by ' || v_prov.display_name ||
      '. Hailed on WorkHive and closed out through the platform.',
    'marketplace', true, v_prov.auth_uid)   -- community_posts.category is a CLOSED vocabulary; 'marketplace' is the sanctioned one
  returning id into v_id;

  update public.service_requests
     set showcase_post_id = v_id, showcase_consent = true, updated_at = now()
   where id = p_request_id;

  return jsonb_build_object('published', true, 'post_id', v_id);
end $$;

comment on function public.publish_service_showcase(uuid) is
  'J26: publishes a CONSENTED completion story. Client-only, finished-jobs-only, once. The text is composed server-side (provider + trade + city) so the showcase can never become a free-text broadcast channel, and it never carries the client name or the site address.';

grant execute on function public.publish_service_showcase(uuid) to authenticated;

-- ── J25: the liquidity leaderboard ──────────────────────────────────────────────────
drop view if exists public.v_service_provider_leaderboard;
create view public.v_service_provider_leaderboard
with (security_invoker = false) as
select
  t.id, t.display_name, t.categories, t.service_areas, t.verified,
  t.completed_jobs, t.rating_avg, t.rating_count, t.tier,
  rank() over (order by t.completed_jobs desc, coalesce(t.rating_avg, 0) desc, t.display_name) as rank,
  1                        as _source_count,
  t._freshness_ts          as _freshness_ts,
  'service_leaderboard:v1' as _canonical_version
from public.v_service_provider_truth t
where t.completed_jobs > 0;

comment on view public.v_service_provider_leaderboard is
  'J25 liquidity engine: top providers ranked over ALREADY-guarded truth (verified completions + VIEW-computed rating from birth-guarded reviews). It introduces no new trust signal, so there is nothing here to forge that is not already unforgeable upstream.';

grant select on public.v_service_provider_leaderboard to anon, authenticated;

insert into public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values
  ('service_leaderboard', 'view', 'v_service_provider_leaderboard', 'marketplace', 'on_demand',
   '{"ranks_on": ["completed_jobs", "rating_avg"], "source": "v_service_provider_truth - no stored counters"}'::jsonb,
   'Top-provider leaderboard for the community liquidity surface; ranks only providers with a real completion.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind = excluded.source_kind, source_name = excluded.source_name,
      owner_skill = excluded.owner_skill, freshness = excluded.freshness,
      contract = excluded.contract, description = excluded.description;

COMMIT;
