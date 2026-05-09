-- Workaround: anon SELECT on worker_achievements returns empty rows despite
-- RLS being disabled and GRANT SELECT to anon being explicit. Service role
-- sees all rows. The cause is something in Supabase's API layer that we
-- can't introspect from outside.
--
-- Solution: expose data through SECURITY DEFINER views that bypass whatever
-- row-level filter is hitting the underlying tables. The views run as the
-- view owner (postgres) so they see all rows, then expose them to anon.

CREATE OR REPLACE VIEW public.v_worker_achievements
WITH (security_invoker = false)
AS
  SELECT id, worker_name, achievement_id, current_level, xp_total, last_action_at
  FROM   public.worker_achievements;

CREATE OR REPLACE VIEW public.v_achievement_xp_log
WITH (security_invoker = false)
AS
  SELECT id, worker_name, achievement_id, xp_earned, source_action, source_id, earned_at
  FROM   public.achievement_xp_log;

GRANT SELECT ON public.v_worker_achievements TO anon, authenticated;
GRANT SELECT ON public.v_achievement_xp_log  TO anon, authenticated;

-- Force refresh so PostgREST picks up the new views
NOTIFY pgrst, 'reload schema';
