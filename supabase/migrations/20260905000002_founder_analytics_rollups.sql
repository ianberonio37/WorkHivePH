-- founder-console analytics rollups (2026-09-05, P-C "cap is not a total", P155).
--
-- The console counted "active hives (30d)", "MAU (30d)" and the 7-day page heatmap CLIENT-SIDE from
-- capped reads of analytics_events: .limit(10000) / .limit(50000) / .limit(20000) against 155,044 rows
-- in the 30-day window and 45,731 in the 7-day window. Every one of those tiles was a wrong number.
-- The MAU read also keyed anonymous rows on Math.random(), so each anon page view counted as a user.
--
-- These three STABLE, SECURITY INVOKER functions roll the truth up in the database. RLS on
-- analytics_events still applies to the caller (analytics_events_select_admin), so a non-admin
-- gets 0 rows, exactly as the page's gate expects. "MAU" counts IDENTIFIED viewers (auth_uid or worker_name):
-- measured 2026-09-05, 37,823 distinct anonymous sessions sat beside 20 identified viewers in 30 days, so an
-- anon-inclusive figure is crawler traffic, not users. Anonymous sessions are a separate rollup.
CREATE OR REPLACE FUNCTION public.founder_active_hives(p_days integer DEFAULT 30)
RETURNS bigint
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = public
AS $$
  SELECT count(DISTINCT hive_id)
  FROM analytics_events
  WHERE hive_id IS NOT NULL
    AND created_at >= now() - make_interval(days => GREATEST(p_days, 1));
$$;

CREATE OR REPLACE FUNCTION public.founder_mau(p_days integer DEFAULT 30)
RETURNS bigint
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = public
AS $$
  SELECT count(DISTINCT COALESCE(auth_uid::text, worker_name))
  FROM analytics_events
  WHERE event_name = 'page_view'
    AND (auth_uid IS NOT NULL OR worker_name IS NOT NULL)
    AND created_at >= now() - make_interval(days => GREATEST(p_days, 1));
$$;

CREATE OR REPLACE FUNCTION public.founder_anon_sessions(p_days integer DEFAULT 30)
RETURNS bigint
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = public
AS $$
  SELECT count(DISTINCT session_id)
  FROM analytics_events
  WHERE event_name = 'page_view'
    AND auth_uid IS NULL AND worker_name IS NULL AND session_id IS NOT NULL
    AND created_at >= now() - make_interval(days => GREATEST(p_days, 1));
$$;

CREATE OR REPLACE FUNCTION public.founder_page_heatmap(p_days integer DEFAULT 7)
RETURNS TABLE(page text, views bigint, unique_users bigint)
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = public
AS $$
  SELECT page,
         count(*)::bigint AS views,
         count(DISTINCT COALESCE(auth_uid::text, worker_name, session_id, 'anon'))::bigint AS unique_users
  FROM analytics_events
  WHERE event_name = 'page_view'
    AND page IS NOT NULL
    AND created_at >= now() - make_interval(days => GREATEST(p_days, 1))
  GROUP BY page
  ORDER BY views DESC;
$$;

-- 14-day DAU series: identified viewers per Manila day (the client scan was .limit(20000) over ~90k rows).
CREATE OR REPLACE FUNCTION public.founder_dau_series(p_days integer DEFAULT 14)
RETURNS TABLE(day date, dau bigint, events bigint)
LANGUAGE sql STABLE SECURITY INVOKER
SET search_path = public
AS $$
  SELECT (created_at AT TIME ZONE 'Asia/Manila')::date AS day,
         count(DISTINCT COALESCE(auth_uid::text, worker_name)) FILTER (WHERE auth_uid IS NOT NULL OR worker_name IS NOT NULL)::bigint AS dau,
         count(*)::bigint AS events
  FROM analytics_events
  WHERE event_name = 'page_view'
    AND created_at >= (date_trunc('day', now() AT TIME ZONE 'Asia/Manila') - make_interval(days => GREATEST(p_days, 1) - 1)) AT TIME ZONE 'Asia/Manila'
  GROUP BY 1
  ORDER BY 1;
$$;

REVOKE ALL ON FUNCTION public.founder_active_hives(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.founder_dau_series(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.founder_mau(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.founder_anon_sessions(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.founder_page_heatmap(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.founder_active_hives(integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.founder_dau_series(integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.founder_mau(integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.founder_anon_sessions(integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.founder_page_heatmap(integer) TO authenticated;
