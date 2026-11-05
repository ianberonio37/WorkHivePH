-- ★A REMOVED MEMBER COULD NO LONGER READ THEIR OWN XP HISTORY (2026-11-05, GJ M8 J14 hand-off 4, "the leaver's own
-- achievements stay theirs").
--
-- achievement_xp_log is keyed by worker_name (it carries no auth_uid), and its read policy and my_recent_xp() admit the
-- names auth_worker_names() returns. That function returns a person's names from their ACTIVE memberships, their seller
-- name, and - only for someone with no membership row at all - their display name. A member a supervisor removed has a
-- membership row ('kicked') and no active one, so it returned NOTHING: their achievements page kept its totals (read by
-- auth_uid) and showed "No XP this week" and an empty Recent XP for work they had just logged - while the removal notice
-- told them their achievements stay theirs.
--
-- auth_worker_names() also decides marketplace inserts and owner read-write tables, so it is NOT widened. A read-only
-- sibling, auth_own_history_names(), adds the names of the person's own REMOVED memberships - each guarded against a
-- namesake, exactly as the display-name branch is - and only the XP log's read policy and my_recent_xp() use it.

CREATE OR REPLACE FUNCTION public.auth_own_history_names()
RETURNS SETOF text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $$
  select public.auth_worker_names()
  union
  select m.worker_name from public.hive_members m
   where m.auth_uid = auth.uid() and m.status = 'kicked' and m.worker_name is not null
     and not exists (select 1 from public.hive_members o
                      where o.worker_name = m.worker_name and o.auth_uid is distinct from auth.uid())
     and not exists (select 1 from public.worker_profiles p
                      where p.display_name = m.worker_name and p.auth_uid <> auth.uid())
$$;

-- anon is named: Supabase grants it EXECUTE explicitly on every new function (definer-doors Y2)
REVOKE ALL ON FUNCTION public.auth_own_history_names() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.auth_own_history_names() TO authenticated;

DROP POLICY IF EXISTS ach_log_owner_read ON public.achievement_xp_log;
CREATE POLICY ach_log_owner_read ON public.achievement_xp_log
  FOR SELECT
  USING (worker_name IN (SELECT public.auth_own_history_names()));

CREATE OR REPLACE FUNCTION public.my_recent_xp(p_limit integer DEFAULT 30)
RETURNS TABLE(achievement_id text, xp_earned integer, source_action text, earned_at timestamp with time zone)
LANGUAGE sql
STABLE
SET search_path TO 'public'
AS $function$
  select x.achievement_id, x.xp_earned, x.source_action, x.earned_at
    from unnest(array(select public.auth_own_history_names())) n(name)
    cross join lateral (
      select l.id, l.achievement_id, l.xp_earned, l.source_action, l.earned_at
        from public.achievement_xp_log l
       where l.worker_name = n.name
       order by l.earned_at desc, l.id
       limit greatest(1, least(coalesce(p_limit, 30), 200))
    ) x
   order by x.earned_at desc, x.id
   limit greatest(1, least(coalesce(p_limit, 30), 200))
$function$;
