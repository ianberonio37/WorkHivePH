-- 20261026000012_what_failed_on_peoples_screens.sql
--
-- WHAT A PERSON'S BROWSER REPORTED REACHED NO ONE (OWN dependency lens, 2026-10-26). utils.js whLogError has written
-- every uncaught error, refused write and failed call to public.client_errors since 2026-07-23 - and no page, panel or
-- dashboard read the table. A dependency that went down (the calculation service, map tiles, a library CDN) was
-- therefore invisible to the founder even when each page fell back gracefully. The dependency fixes log as
-- context 'dependency:<host>:<kind>'; this read gives the operator console those failures and every other one.
--
-- Totals, never rows (the console's K4 rule): grouped by context and page over a window of 1-90 days, with how many
-- times, how many distinct people (an account, else a device), when last, and the newest message. A platform admin
-- only (K5), SECURITY DEFINER so the table's own RLS - each person their own rows - does not hide the platform from it.

CREATE OR REPLACE FUNCTION public.founder_client_errors(p_days integer DEFAULT 7)
RETURNS TABLE (
  context   text,
  page      text,
  times     bigint,
  people    bigint,
  last_seen timestamptz,
  sample    text
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  IF NOT public.is_platform_admin() THEN
    RAISE EXCEPTION 'Only a platform admin can read what failed on people''s screens' USING ERRCODE = '42501';
  END IF;
  RETURN QUERY
  SELECT e.context, coalesce(e.page, '(no page)'), count(*),
         count(DISTINCT coalesce(e.auth_uid::text, e.user_agent, e.worker_name, '?')),
         max(e.created_at),
         (array_agg(left(coalesce(e.shown, e.message), 200) ORDER BY e.created_at DESC))[1]
    FROM public.client_errors e
   WHERE e.created_at > now() - make_interval(days => least(greatest(coalesce(p_days, 7), 1), 90))
   GROUP BY e.context, coalesce(e.page, '(no page)')
   ORDER BY max(e.created_at) DESC
   LIMIT 50;
END
$$;
REVOKE ALL ON FUNCTION public.founder_client_errors(integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.founder_client_errors(integer) TO authenticated;
