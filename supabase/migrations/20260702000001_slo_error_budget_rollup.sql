-- Arc T / T3: queryable SLO error-budget rollup over wh_traces.
-- ============================================================================
-- GATEWAY_SLO.md declares availability 99.5% / error-rate < 1% over a 28-day
-- window. wh_traces is ERROR-dense (the T2 `serveObserved` wrapper writes a row
-- on every UNHANDLED throw) plus some success traces, so a TRUE platform-wide
-- error RATE denominator is k6-sourced (GATEWAY_SLO §5). This rollup computes
-- the ERROR side HONESTLY: per-route error counts over rolling windows, and an
-- error-budget burn given a caller-supplied expected request volume (from k6 or
-- a configured baseline) — never a fake denominator from the error-dense table.
--
-- "Error" = HTTP status >= 500 OR a non-null error_code, EXCLUDING intended
-- policy rejections 401 (auth) / 403 (tenancy) / 429 (rate-limit/quota), which
-- are policy-working-as-designed and tracked as enforcement counters, not
-- failures (GATEWAY_SLO §1 note).

-- ── View: per-route error rollup over rolling windows (28d / 6h / 1h) ─────────
-- canonical-allow: observability/SLO infrastructure over wh_traces (the trace spine),
-- NOT a user-facing KPI truth view — it has no page/dashboard anchor by design.
create or replace view v_wh_traces_slo
  with (security_invoker = on)   -- respect wh_traces RLS: the SLO tool runs as service_role (bypasses RLS);
                                 -- a regular caller sees only RLS-permitted rows, never cross-tenant traces.
as
select
  route,
  count(*)                                                                 as traced_total,
  count(*) filter (
    where (status >= 500 or error_code is not null)
      and coalesce(status, 0) not in (401, 403, 429)
  )                                                                        as error_count,
  count(*) filter (where status in (401, 403, 429))                        as policy_rejections,
  count(*) filter (
    where created_at >= now() - interval '6 hours'
      and (status >= 500 or error_code is not null)
      and coalesce(status, 0) not in (401, 403, 429)
  )                                                                        as errors_6h,
  count(*) filter (
    where created_at >= now() - interval '1 hour'
      and (status >= 500 or error_code is not null)
      and coalesce(status, 0) not in (401, 403, 429)
  )                                                                        as errors_1h,
  min(created_at)                                                          as first_seen,
  max(created_at)                                                          as last_seen
from wh_traces
where created_at >= now() - interval '28 days'
group by route;

comment on view v_wh_traces_slo is
  'Arc T/T3 SLO error rollup over wh_traces: per-route error counts (excl. 401/403/429 policy rejections) over 28d/6h/1h windows. RATE denominator is k6-sourced; this is the error-side SLI numerator.';

-- ── RPC: error-budget burn given an expected request volume ──────────────────
-- burn = observed_error_rate / SLO_error_budget(1%). burn >= 1 => over budget.
-- Multi-window alerting (fast 1h + slow 6h) is composed by the caller
-- (tools/slo_burn_check.py) — this RPC answers one (route, window, volume).
create or replace function slo_error_budget(
  p_route             text default null,
  p_window_min        int  default 60,
  p_expected_requests int  default null   -- k6/config volume for the window
)
returns table (
  route             text,
  error_count       bigint,
  window_min        int,
  expected_requests int,
  error_rate_pct    numeric,
  budget_burn       numeric,
  status            text
)
language sql
stable
as $$
  with e as (
    select t.route as r, count(*) as errs
    from wh_traces t
    where t.created_at >= now() - make_interval(mins => p_window_min)
      and (t.status >= 500 or t.error_code is not null)
      and coalesce(t.status, 0) not in (401, 403, 429)
      and (p_route is null or t.route = p_route)
    group by t.route
  )
  select
    e.r,
    e.errs,
    p_window_min,
    p_expected_requests,
    case when coalesce(p_expected_requests, 0) = 0 then null
         else round((e.errs::numeric / p_expected_requests) * 100, 3) end,
    case when coalesce(p_expected_requests, 0) = 0 then null
         else round((e.errs::numeric / p_expected_requests) / 0.01, 3) end,
    case
      when coalesce(p_expected_requests, 0) = 0 then 'unknown_volume'
      when (e.errs::numeric / p_expected_requests) / 0.01 >= 2 then 'critical'
      when (e.errs::numeric / p_expected_requests) / 0.01 >= 1 then 'warning'
      else 'ok'
    end
  from e;
$$;

comment on function slo_error_budget(text, int, int) is
  'Arc T/T3 error-budget burn for a route/window given an expected request volume (k6-sourced). burn = error_rate / 1% SLO budget; status ok/warning(>=1)/critical(>=2)/unknown_volume.';
