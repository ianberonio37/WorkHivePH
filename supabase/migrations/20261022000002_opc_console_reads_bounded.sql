-- OPC step 0 (2026-10-22): the operator console reads totals, never rows - and every hive's, not the reader's own.
--
-- founder-console.html is being un-retired as the one operator console. Retired, it still pulled up to ~77,000 rows a
-- visit to add them up in the browser: page views for the 30-day hive Pareto (capped at 50,000), AI cost by provider and
-- hive for 7 days (20,000), AI cost today (5,000), the readiness stairs (2,000), the marketplace pulse (5,000) and the
-- whole credit ledger (no limit at all; it reads get_credit_ledger_totals now). Each read is now one call that returns the
-- numbers the page paints, worked out where the rows are.
--
-- ★A PLATFORM FIGURE READ THROUGH THE READER'S OWN RLS IS THE READER'S SLICE. Measured as the platform admin the
-- console is for: v_hive_readiness_truth showed 1 of 7 hives, v_hives_truth 1 of 7, hive_audit_log 28,833 of 121,943
-- rows - so the maturity panel, the hive names and "Recent admin activity" described the admin's own hive while their
-- labels said the platform. These reads answer platform-wide questions, so they run SECURITY DEFINER and ask
-- is_platform_admin() first (42501 for anyone else) - the same contract as the generated console_read_* reads.

-- the 30-day hive Pareto: page views per hive, the ten busiest by name, and the share the busiest tenth holds
create or replace function public.founder_hive_pareto(p_days integer default 30)
returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
declare r jsonb;
begin
  if not public.is_platform_admin() then
    raise exception 'Only platform admins can read the operator console.' using errcode = '42501';
  end if;
  with by_hive as (
    select hive_id, count(*)::bigint as events
    from analytics_events
    where event_name = 'page_view' and hive_id is not null
      and created_at >= now() - make_interval(days => greatest(p_days, 1))
    group by hive_id
  ), ranked as (
    select hive_id, events, row_number() over (order by events desc, hive_id) as rn, count(*) over () as n
    from by_hive
  ), tot as (select coalesce(sum(events), 0) as total from by_hive)
  select jsonb_build_object(
    'top', coalesce((select jsonb_agg(jsonb_build_object('hive_id', k.hive_id, 'hive_name', h.name, 'events', k.events)
                                      order by k.rn)
                     from ranked k left join v_hives_truth h on h.id = k.hive_id where k.rn <= 10), '[]'::jsonb),
    'total', (select total from tot),
    'n_hives', (select count(*) from by_hive),
    'top10pct_share', case when (select total from tot) = 0 then 0
      else round((select sum(events) from ranked where rn <= greatest(1, ceil(n * 0.1)))::numeric
                 / (select total from tot), 4) end
  ) into r;
  return r;
end $$;

-- AI cost in a window: calls, how many recorded a cost, the total, by provider, and the five hives spending most.
-- A call whose cost was never recorded is not a free call: a sum over no recorded cost is null, said as "no cost
-- recorded", never a confident $0.00 (whFmtPeso's rule, the same one for dollars).
create or replace function public.founder_ai_cost(p_from timestamptz, p_to timestamptz default now())
returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
declare r jsonb;
begin
  if not public.is_platform_admin() then
    raise exception 'Only platform admins can read the operator console.' using errcode = '42501';
  end if;
  with w as (
    select coalesce(nullif(provider, ''), 'unknown') as provider, hive_id, cost_usd
    from ai_cost_log where created_at >= p_from and created_at < p_to
  )
  select jsonb_build_object(
    'n_calls', (select count(*) from w),
    'n_priced', (select count(cost_usd) from w),
    'total', (select sum(cost_usd) from w),
    'providers', coalesce((select jsonb_agg(jsonb_build_object('provider', provider, 'cost', cost) order by cost desc nulls last, provider)
                           from (select provider, sum(cost_usd) as cost from w group by provider) p), '[]'::jsonb),
    'top_hives', coalesce((select jsonb_agg(jsonb_build_object('hive_id', t.hive_id, 'hive_name', h.name, 'cost', t.cost)
                                            order by t.cost desc, t.hive_id)
                           from (select hive_id, sum(cost_usd) as cost from w where hive_id is not null and cost_usd is not null
                                 group by hive_id order by sum(cost_usd) desc, hive_id limit 5) t
                           left join v_hives_truth h on h.id = t.hive_id), '[]'::jsonb),
    -- the workers' ratings of AI answers in the same window (ai_reply_feedback: +1 / -1), every hive's
    'ratings_up', (select count(*) from ai_reply_feedback where rating = 1 and created_at >= p_from and created_at < p_to),
    'ratings_down', (select count(*) from ai_reply_feedback where rating = -1 and created_at >= p_from and created_at < p_to)
  ) into r;
  return r;
end $$;

-- readiness: every hive's latest snapshot - the stairs, the median and the five that most need a hand, by name
create or replace function public.founder_maturity()
returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
declare r jsonb;
begin
  if not public.is_platform_admin() then
    raise exception 'Only platform admins can read the operator console.' using errcode = '42501';
  end if;
  with x as (
    select hive_id, coalesce(current_stair, 0) as stair, composite_score, blocker_summary from v_hive_readiness_truth
  ), scored as (
    select composite_score, row_number() over (order by composite_score) - 1 as i, count(*) over () as n
    from x where composite_score is not null
  )
  select jsonb_build_object(
    'stairs', (select jsonb_agg(coalesce(c.c, 0) order by s.s)
               from generate_series(0, 4) as s(s)
               left join (select stair, count(*) as c from x group by stair) c on c.stair = s.s),
    -- the same median the page took: the middle of the sorted scores (the upper middle for an even count)
    'median', (select composite_score from scored where i = floor(n / 2)),
    'total', (select count(*) from x),
    'bottom', coalesce((select jsonb_agg(jsonb_build_object('hive_id', b.hive_id, 'hive_name', h.name, 'score', b.score,
                                                            'blocker', b.blocker_summary) order by b.score, b.hive_id)
                        from (select hive_id, coalesce(composite_score, 0) as score, blocker_summary from x
                              order by coalesce(composite_score, 0), hive_id limit 5) b
                        left join v_hives_truth h on h.id = b.hive_id), '[]'::jsonb)
  ) into r;
  return r;
end $$;

-- the marketplace pulse, from the listings truth view
create or replace function public.founder_marketplace_pulse()
returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
declare r jsonb;
begin
  if not public.is_platform_admin() then
    raise exception 'Only platform admins can read the operator console.' using errcode = '42501';
  end if;
  select jsonb_build_object(
    'published', count(*) filter (where status = 'published'),
    'value_listed_php', coalesce(sum(price) filter (where status = 'published'), 0),
    'sold_total', count(*) filter (where status = 'sold'),
    'awaiting_review', count(*) filter (where status = 'draft'),
    'sellers', count(distinct seller_name) filter (where status = 'published' and coalesce(seller_name, '') <> ''),
    'total_listings', count(*)
  ) into r
  from v_marketplace_listings_truth;
  return r;
end $$;

-- (the credit totals are not here: the console's credit position reads get_credit_ledger_totals, the rollup Platform
-- Actions' queue code already calls - migration 20261020000002 - so a second copy would only drift from it)

-- the latest admin activity across every hive (the console showed the admin's own 24 % of hive_audit_log)
create or replace function public.founder_audit_feed(p_limit integer default 50)
returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
declare r jsonb;
begin
  if not public.is_platform_admin() then
    raise exception 'Only platform admins can read the operator console.' using errcode = '42501';
  end if;
  select coalesce(jsonb_agg(jsonb_build_object('id', a.id, 'action', a.action, 'actor', a.actor, 'target_type', a.target_type,
                                               'target_name', a.target_name, 'hive_id', a.hive_id, 'hive_name', h.name,
                                               'created_at', a.created_at) order by a.created_at desc, a.id), '[]'::jsonb)
  into r
  from (select id, action, actor, target_type, target_name, hive_id, created_at from hive_audit_log
        order by created_at desc, id limit least(greatest(p_limit, 1), 200)) a
  left join v_hives_truth h on h.id = a.hive_id;
  return r;
end $$;

revoke all on function public.founder_hive_pareto(integer) from public, anon;
revoke all on function public.founder_ai_cost(timestamptz, timestamptz) from public, anon;
revoke all on function public.founder_maturity() from public, anon;
revoke all on function public.founder_marketplace_pulse() from public, anon;
revoke all on function public.founder_audit_feed(integer) from public, anon;
grant execute on function public.founder_hive_pareto(integer) to authenticated;
grant execute on function public.founder_ai_cost(timestamptz, timestamptz) to authenticated;
grant execute on function public.founder_maturity() to authenticated;
grant execute on function public.founder_marketplace_pulse() to authenticated;
grant execute on function public.founder_audit_feed(integer) to authenticated;
