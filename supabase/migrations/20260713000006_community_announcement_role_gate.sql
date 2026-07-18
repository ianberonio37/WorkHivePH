-- 20260713000006_community_announcement_role_gate.sql
--
-- Community announcement UI-only-gate bypass (LOW-MED — role impersonation) — bug-hunt 2026-07-13,
-- cross-page UI-only-role-gate sweep.
--
-- community.html:1788 blocks a non-supervisor from posting category='announcement' CLIENT-side only
-- ("Supervisors only can post announcements"). The community_posts_insert RLS gates auth + hive
-- membership but does NOT constrain `category` by role, so a worker can POST an official-looking
-- hive-wide 'announcement' straight through PostgREST, impersonating supervisor authority.
-- LIVE-CONFIRMED (rolled back): bryangarcia (Baguio worker) INSERTed category='announcement' -> stored.
-- Same UI-only-gate class as the api_keys worker-mint (mig 20260712000020, [[reference_xhive_write_hole_siblings_2026_07_13]]).
--
-- FIX: a BEFORE INSERT/UPDATE trigger that rejects category='announcement' unless the caller is a
-- SUPERVISOR of that hive (user_supervisor_hive_ids()). A service-role/seeder insert (auth.uid() NULL)
-- is trusted and bypasses the check.

BEGIN;

CREATE OR REPLACE FUNCTION public.guard_community_announcement() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
BEGIN
  IF NEW.category = 'announcement'
     AND auth.uid() IS NOT NULL
     AND NOT (NEW.hive_id IN (SELECT public.user_supervisor_hive_ids())) THEN
    RAISE EXCEPTION 'Only supervisors can post announcements' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END; $fn$;

DROP TRIGGER IF EXISTS trg_guard_community_announcement ON public.community_posts;
CREATE TRIGGER trg_guard_community_announcement BEFORE INSERT OR UPDATE ON public.community_posts
  FOR EACH ROW EXECUTE FUNCTION public.guard_community_announcement();

COMMIT;
