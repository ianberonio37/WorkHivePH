-- OPC (2026-10-22): the operator console's Developer tab - what the builder watches, platform-wide, in one admin read.
--
-- llm-observability.html and agentic-rag-observability.html (both retired) worked these out in the browser: up to 5,000
-- ai_cost_log rows for per-task routing, and the viewer's OWN hive's latest 500 RAG traces for the route breakdown, the
-- heaviest queries and the recent traces - a hive member's slice under a platform heading. They are computed here,
-- across every hive, for a platform admin only (SECURITY DEFINER, is_platform_admin() first, 42501 otherwise).
--
-- The per-hive budget is read from ai_rate_limits - the counters the gateway itself enforces (_shared/rate-limit.ts:
-- 50 calls an hour, 300 a day per hive by default) - not re-derived from the cost log against a guessed cap. A window
-- that has already ended counts as 0: the gateway resets it on the hive's next call.

create or replace function public.founder_dev_reads(p_from timestamptz default now() - interval '30 days',
  p_to timestamptz default now())
returns jsonb language plpgsql stable security definer set search_path = public, pg_temp as $$
declare r jsonb;
begin
  if not public.is_platform_admin() then
    raise exception 'Only platform admins can read the operator console.' using errcode = '42501';
  end if;
  with calls as (
    select coalesce(fn, 'unknown') as fn, provider, model, latency_ms, status, total_tokens, cost_usd,
           (provider ilike '%ai_cache%' or model like 'cache:%') as cached
    from ai_cost_log where created_at >= p_from and created_at < p_to
  ), routing as (
    -- one row per task: how it is routed (cache, providers, latency) and what it costs (tokens, the recorded spend - null
    -- when no call recorded a price, never a confident $0 - and the share that did not succeed). ai-quality.html's
    -- per-function spend is this table now, across every hive.
    select c.fn, count(*) as calls,
           round(100.0 * count(*) filter (where c.cached) / nullif(count(*), 0), 1) as cache_pct,
           round(percentile_cont(0.5) within group (order by case when not c.cached then c.latency_ms end)) as p50_ms,
           coalesce(sum(c.total_tokens), 0) as tokens,
           sum(c.cost_usd) as cost,
           round(100.0 * count(*) filter (where c.status is distinct from 'success') / nullif(count(*), 0), 1) as fail_pct,
           (select jsonb_agg(jsonb_build_object('provider', pv, 'calls', n) order by n desc, pv)
              from (select coalesce(split_part(c2.provider, ':', 1), 'unknown') as pv, count(*) as n
                    from calls c2 where c2.fn = c.fn group by 1 order by 2 desc, 1 limit 3) m) as providers
    from calls c group by c.fn
  ), traces as (
    select route, question, retries, grader_passed, checker_passed, total_tokens, latency_ms, created_at
    from agentic_rag_traces where created_at >= p_from and created_at < p_to
  )
  select jsonb_build_object(
    'per_task_routing', coalesce((select jsonb_agg(to_jsonb(x) order by x.calls desc, x.fn) from routing x), '[]'::jsonb),
    'per_hive_budget', coalesce((select jsonb_agg(jsonb_build_object(
        'hive_id', l.hive_id, 'hive_name', h.name,
        'calls_this_hour', case when l.window_start > now() - interval '1 hour' then l.call_count else 0 end,
        'calls_today', case when l.day_window_start > now() - interval '1 day' then l.day_count else 0 end,
        'last_window_start', l.window_start) order by l.window_start desc)
      from ai_rate_limits l left join v_hives_truth h on h.id = l.hive_id), '[]'::jsonb),
    'limit_per_hour', 50,
    'limit_per_day', 300,
    'rag_routes', coalesce((select jsonb_agg(to_jsonb(rr) order by rr.runs desc, rr.route) from (
        select coalesce(route, 'unknown') as route, count(*) as runs,
               round(100.0 * count(*) filter (where coalesce(retries, 0) > 0) / nullif(count(*), 0), 1) as retry_pct,
               round(100.0 * count(*) filter (where checker_passed) / nullif(count(*), 0), 1) as checker_pass_pct,
               round(100.0 * count(*) filter (where grader_passed) / nullif(count(*), 0), 1) as grader_pass_pct,
               round(avg(total_tokens)) as avg_tokens, round(avg(latency_ms)) as avg_latency_ms
        from traces group by 1) rr), '[]'::jsonb),
    'rag_heavy', coalesce((select jsonb_agg(to_jsonb(hv) order by hv.tokens desc nulls last, hv.created_at desc) from (
        select left(question, 90) as question, coalesce(route, 'unknown') as route, total_tokens as tokens,
               latency_ms, created_at
        from traces order by total_tokens desc nulls last, created_at desc limit 10) hv), '[]'::jsonb),
    'rag_recent', coalesce((select jsonb_agg(to_jsonb(rc) order by rc.created_at desc) from (
        select created_at, coalesce(route, 'unknown') as route, left(question, 90) as question,
               checker_passed, latency_ms
        from traces order by created_at desc limit 10) rc), '[]'::jsonb)
  ) into r;
  return r;
end $$;

revoke all on function public.founder_dev_reads(timestamptz, timestamptz) from public, anon;
grant execute on function public.founder_dev_reads(timestamptz, timestamptz) to authenticated;
