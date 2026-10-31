-- ai-quality.html totalled a hive's AI use in the browser, over the rows it read: the latest 2,000 calls and 5,000 ratings
-- of the last 30 days. Wave HS L4 ("a year of the hive", 2026-10-30, walked live) laid an AI-heavy month - 2,973 calls in
-- the window for a hive of thirty - and the page said "Workers used AI 2000 times in the last 30 days" and "Cost, last 30
-- days ₱35.84" against a true ₱54.07, with "over the latest 2,000 calls" in the small print beneath. A cap on a list is a
-- short list; a cap on a sum is a wrong number. These figures are sums, so they are summed where every row is.
--
-- SECURITY INVOKER: the totals are over exactly the rows the reader's RLS lets them read - a supervisor's hive, or a
-- worker's own calls - the same rows the page's two reads returned, without their cap.
create or replace function public.hive_ai_usage_30d(p_hive uuid)
returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
  with c as (
    select coalesce(fn, 'unknown') as fn, status, schema_compliance, coalesce(cost_usd, 0) as cost_usd,
           coalesce(total_tokens, 0) as total_tokens, latency_ms
    from public.ai_cost_log
    where hive_id = p_hive and created_at >= now() - interval '30 days'
  ), f as (
    select rating from public.ai_reply_feedback
    where hive_id = p_hive and created_at >= now() - interval '30 days'
  )
  select jsonb_build_object(
    'total_calls',    (select count(*) from c),
    'total_cost',     (select coalesce(sum(cost_usd), 0) from c),
    'total_tokens',   (select coalesce(sum(total_tokens), 0) from c),
    'fallback_count', (select count(*) from c where status = 'fallback'),
    'success_count',  (select count(*) from c where status = 'success'),
    'schema_ok',      (select count(*) from c where schema_compliance is true),
    'schema_total',   (select count(*) from c where schema_compliance is not null),
    'thumbs_up',      (select count(*) from f where rating = 1),
    'thumbs_down',    (select count(*) from f where rating = -1),
    'fns', coalesce((select jsonb_agg(x order by x.cost desc, x.fn) from (
        select fn, count(*) as calls, sum(total_tokens) as tokens, sum(cost_usd) as cost,
               round(avg(latency_ms) filter (where latency_ms is not null)) as latency_avg,
               count(*) filter (where status is distinct from 'success') as failures
        from c group by fn) x), '[]'::jsonb)
  );
$$;

revoke all on function public.hive_ai_usage_30d(uuid) from public, anon;
grant execute on function public.hive_ai_usage_30d(uuid) to authenticated;
