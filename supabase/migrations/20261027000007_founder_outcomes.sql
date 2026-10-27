-- ★WHAT HAPPENED AFTER THE FIRST VISIT (T2 OUT, 2026-10-27). The console counted visits per page (founder_dau_series,
-- founder_mau) and what each page was used for (founder_feature_use), and nothing said whether anyone CAME BACK. Ian's
-- model ends in usage; this is usage as three figures per page, read from the event ledger the pages already write.
--
-- founder_outcomes(p_days) - one row per page seen in the window, every figure with its own basis:
--   uses_7d / use_accounts_7d / use_sessions_7d
--        uses in the last 7 Manila days (any event that is not a page_view, as founder_feature_use counts them), the
--        signed-in ACCOUNTS and the signed-out SESSIONS apart - one "people" figure would add the two.
--   cohort_7 / returned_7, cohort_30 / returned_30
--        the accounts whose first day on the page in the window is at least 7 (30) days old - a follow-up still running
--        is not a "did not come back" - and of those, the ones with an event on the page on a LATER Manila day within
--        7 (30) days of that first day. Both numbers are returned, never only a rate: 1 of 1 is not 100% of anything.
--   repeat_cohort / repeat_7
--        the accounts whose first USE in the window is at least 7 days old, and of those the ones that used the page on
--        two or more different Manila days within 7 days of it. Called "repeat use", never satisfaction: the feedback
--        form is the only place a person says how they feel (Ian, 2026-10-26).
-- A signed-out session is one visit, so it cannot return; sessions are counted in use only.
-- SECURITY INVOKER like founder_feature_use: analytics_events is readable by the platform admin (and grafana_reader)
-- only, so anyone else is answered with nothing rather than with someone's activity.

create or replace function public.founder_outcomes(p_days integer default 90)
returns table(page text, uses_7d bigint, use_accounts_7d bigint, use_sessions_7d bigint,
              cohort_7 bigint, returned_7 bigint, cohort_30 bigint, returned_30 bigint,
              repeat_cohort bigint, repeat_7 bigint)
language sql
stable
security invoker
set search_path = public
as $$
  with today as (
    select (now() at time zone 'Asia/Manila')::date as t
  ), ev as (
    select coalesce(e.page, e.props ->> 'page') as page,
           e.event_name <> 'page_view'          as is_use,
           e.auth_uid, e.session_id,
           (e.created_at at time zone 'Asia/Manila')::date as d
      from public.analytics_events e
     where e.created_at >= now() - make_interval(days => greatest(p_days, 31))
  ), days as (
    select distinct page, auth_uid, d from ev where auth_uid is not null and page is not null
  ), first_day as (
    select page, auth_uid, min(d) as d0 from days group by 1, 2
  ), ret as (
    select f.page, f.d0,
           bool_or(x.d > f.d0 and x.d <= f.d0 + 7)  as r7,
           bool_or(x.d > f.d0 and x.d <= f.d0 + 30) as r30
      from first_day f join days x on x.page = f.page and x.auth_uid = f.auth_uid
     group by f.page, f.auth_uid, f.d0
  ), ret_by_page as (
    select r.page,
           count(*) filter (where r.d0 <= t.t - 7)              as cohort_7,
           count(*) filter (where r.d0 <= t.t - 7 and r.r7)     as returned_7,
           count(*) filter (where r.d0 <= t.t - 30)             as cohort_30,
           count(*) filter (where r.d0 <= t.t - 30 and r.r30)   as returned_30
      from ret r cross join today t
     group by r.page
  ), use_days as (
    select distinct page, auth_uid, d from ev where is_use and auth_uid is not null and page is not null
  ), first_use as (
    select page, auth_uid, min(d) as u0 from use_days group by 1, 2
  ), rep as (
    select f.page, f.u0, count(distinct x.d) filter (where x.d <= f.u0 + 7) as n_days
      from first_use f join use_days x on x.page = f.page and x.auth_uid = f.auth_uid
     group by f.page, f.auth_uid, f.u0
  ), rep_by_page as (
    select r.page,
           count(*) filter (where r.u0 <= t.t - 7)                    as repeat_cohort,
           count(*) filter (where r.u0 <= t.t - 7 and r.n_days >= 2)  as repeat_7
      from rep r cross join today t
     group by r.page
  ), use_by_page as (
    select e.page,
           count(*)                                                  as uses_7d,
           count(distinct e.auth_uid)                                as use_accounts_7d,
           count(distinct e.session_id) filter (where e.auth_uid is null) as use_sessions_7d
      from ev e cross join today t
     where e.is_use and e.page is not null and e.d > t.t - 7
     group by e.page
  ), pages as (
    select distinct page from ev where page is not null
  )
  select p.page,
         coalesce(u.uses_7d, 0)::bigint, coalesce(u.use_accounts_7d, 0)::bigint, coalesce(u.use_sessions_7d, 0)::bigint,
         coalesce(r.cohort_7, 0)::bigint, coalesce(r.returned_7, 0)::bigint,
         coalesce(r.cohort_30, 0)::bigint, coalesce(r.returned_30, 0)::bigint,
         coalesce(s.repeat_cohort, 0)::bigint, coalesce(s.repeat_7, 0)::bigint
    from pages p
    left join use_by_page u on u.page = p.page
    left join ret_by_page r on r.page = p.page
    left join rep_by_page s on s.page = p.page
   order by 2 desc, 5 desc, 1;
$$;

revoke execute on function public.founder_outcomes(integer) from public, anon;
grant execute on function public.founder_outcomes(integer) to authenticated, service_role;

comment on function public.founder_outcomes(integer) is
  'Per page: uses in 7 Manila days (accounts and signed-out sessions apart); accounts that came back on a later day within 7 / 30 days of their first day in the window (complete follow-up only, cohort beside the count); repeat use = used on 2+ days within 7 days of the first use. SECURITY INVOKER: platform admin only through analytics_events RLS.';
