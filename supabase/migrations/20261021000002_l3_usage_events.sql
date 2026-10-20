-- SL L3 - a page's USE is recorded as events someone can count (2026-10-21).
--
-- Measured before this change: 31 pages log a page_view and 30 of them record nothing else. The table's own
-- migration (20260513000000) promised "feature pages ALSO emit feature_use"; only resume.html ever did. The operator
-- could count VISITS per page (founder_page_heatmap) and never what a page was USED for. And the counts by person and
-- by hive were counts of claims: bind_analytics_events_submitter() returned early for a request with no auth.uid(),
-- so an anonymous insert kept whatever auth_uid it sent (anyone could log events as any account), and for everyone
-- hive_id and worker_name were whatever the device remembered - a stale hive, a remembered name.
--
-- 1. The binder decides who, which hive and what name - never the page:
--      a visitor (role anon)   -> no account, no hive, no name
--      a signed-in person      -> auth_uid = auth.uid(); hive_id kept only while they are an ACTIVE member of it;
--                                 worker_name = their profile's name, else their name in that hive (the rule
--                                 wh_bind_audit_actor applies to the trail), else none
--      service role / a direct database session -> states its own fields (edge functions, seeders)
--    and for every row, props keep only short plain values under keys that cannot carry a person or their words.
-- 2. founder_feature_use(p_days): what each page was used for - every event that is not a page_view, by page and
--    action (resume's resume_* events count under their own names, so their history stays countable), with the
--    signed-in ACCOUNTS and the signed-out SESSIONS counted apart: one figure called "people" would add the two.
-- 3. A partial index so that read touches only use events, not the page views that are 99% of the table.

create or replace function public.bind_analytics_events_submitter()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_uid    uuid := auth.uid();
  v_claims text := current_setting('request.jwt.claims', true);
  v_role   text := case when v_claims is null or v_claims = '' then null
                        else coalesce(v_claims::jsonb ->> 'role', '') end;
begin
  -- props: short plain values only, never a key that names a person or holds their words
  new.props := coalesce((
    select jsonb_object_agg(e.key, e.value)
      from jsonb_each(case when jsonb_typeof(new.props) = 'object' then new.props else '{}'::jsonb end) as e
     where lower(e.key) !~ '^(email|phone|mobile|name|full_?name|display_?name|worker_?name|author|message|content|body|text|notes?|comment|address|password|token|query|q)$'
       and jsonb_typeof(e.value) in ('number', 'boolean', 'string')
       and (jsonb_typeof(e.value) <> 'string' or length(e.value #>> '{}') <= 60)), '{}'::jsonb);
  new.page := left(new.page, 80);

  -- a direct database session (no request at all) or an edge function on the service role states its own fields
  if v_role is null or v_role = 'service_role' then
    return new;
  end if;

  if v_uid is null then
    new.auth_uid := null;
    new.hive_id := null;
    new.worker_name := null;
    return new;
  end if;

  new.auth_uid := v_uid;
  if new.hive_id is not null and not exists (
       select 1 from public.hive_members hm
        where hm.hive_id = new.hive_id and hm.auth_uid = v_uid and hm.status = 'active') then
    new.hive_id := null;
  end if;
  new.worker_name := coalesce(
    (select wp.display_name from public.worker_profiles wp where wp.auth_uid = v_uid limit 1),
    (select hm.worker_name from public.hive_members hm
      where hm.auth_uid = v_uid and hm.hive_id = new.hive_id and hm.status = 'active' limit 1));
  return new;
end
$$;
revoke all on function public.bind_analytics_events_submitter() from public, anon, authenticated;

create index if not exists idx_analytics_events_use_created
  on public.analytics_events (created_at desc) where event_name <> 'page_view';

create or replace function public.founder_feature_use(p_days integer default 30)
returns table(page text, action text, uses bigint, accounts bigint, visitor_sessions bigint)
language sql
stable
security invoker
set search_path = public
as $$
  select coalesce(e.page, e.props ->> 'page')                                           as page,
         coalesce(nullif(e.props ->> 'action', ''), e.event_name)                      as action,
         count(*)::bigint                                                               as uses,
         count(distinct e.auth_uid)::bigint                                             as accounts,
         count(distinct e.session_id) filter (where e.auth_uid is null)::bigint         as visitor_sessions
    from public.analytics_events e
   where e.event_name <> 'page_view'
     and e.created_at >= now() - make_interval(days => greatest(p_days, 1))
   group by 1, 2
   order by uses desc, page, action;
$$;
revoke all on function public.founder_feature_use(integer) from public, anon;   -- BRH-Y: Supabase grants anon EXECUTE explicitly, so "from public" alone never reached it
grant execute on function public.founder_feature_use(integer) to authenticated;
