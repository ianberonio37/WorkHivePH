-- P6 concurrent-admin edit (bug-hunt roadmap, 2026-07-18, founder-console saveDrawerChanges).
-- Two founders/admins triaging the SAME platform_feedback row blind-overwrite each other:
-- admin_note (free text), priority, status, and is_public. is_public is the consequential one — it
-- PUBLISHES the row to the public /feedback/ roadmap. A stale is_public=true could re-expose a row
-- another admin just un-published (contact emails / worker names re-leaked), or an admin_note is lost.
-- The dispute-resolve flow already has a state-lock (.neq('status','resolved')); the feedback triage
-- had no guard AND platform_feedback had no updated_at. Fix: add updated_at + the shared touch trigger
-- so the client can guard .eq('updated_at', snapshot) and treat a 0-row update as a conflict.
ALTER TABLE public.platform_feedback ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
DROP TRIGGER IF EXISTS tg_touch_platform_feedback ON public.platform_feedback;
CREATE TRIGGER tg_touch_platform_feedback BEFORE UPDATE ON public.platform_feedback
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();
