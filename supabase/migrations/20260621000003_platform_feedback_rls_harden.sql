-- Arc J (Realtime) keystone — platform_feedback realtime-publication leak.
--
-- platform_feedback is in the `supabase_realtime` publication AND carried three anon
-- USING(true) policies (SELECT / UPDATE / DELETE). The Arc J realtime lens re-examined it
-- (a rolled-back two-tenant probe) and proved that any anon (no-JWT) client could:
--   • READ private (is_public=false) feedback INCLUDING contact_email PII + body,
--   • UPDATE (tamper) any row,
--   • DELETE any row,
-- and — because the table is published — subscribe to a Realtime channel and receive a LIVE
-- stream of every feedback submission platform-wide (live PII exfiltration).
--
-- Arc G's permissive-bypass gate had EXEMPTED this table as "global public product-feedback
-- board — cross-hive by design." That exemption was classified by SURFACE HEURISTIC, not by
-- evidence: "public board" means the public reads PUBLISHED (is_public=true) items — it does
-- NOT mean anon gets unrestricted read/write of the whole table including private rows. The
-- evidence retracts the exemption (see [[feedback_classify_by_evidence_not_heuristic]]).
--
-- This migration scopes each verb to its real audience without breaking any live path:
--   • Public /feedback/ roadmap        → SELECT is_public=true only  (was already its query filter)
--   • Anon feedback widget submit       → INSERT, but cannot self-publish or pre-triage
--   • Founder Console (authenticated)   → SELECT/UPDATE/DELETE all, gated to platform admins
--   • Upvotes                           → unaffected (go through SECURITY DEFINER toggle_feedback_upvote)
--
-- Forward-only. No data change.

-- ── Admin predicate ─────────────────────────────────────────────────────────
-- Is the current authenticated user a platform admin? DEFINER so it can read
-- worker_profiles + marketplace_platform_admins regardless of caller RLS;
-- search_path pinned; returns FALSE for anon (auth.uid() IS NULL).
-- Mirrors the proven analytics_events_select_admin EXISTS pattern, factored into a helper
-- (twin of Arc G/H user_hive_ids() / user_can_access_hive()).
CREATE OR REPLACE FUNCTION public.is_platform_admin()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.worker_profiles wp
    JOIN public.marketplace_platform_admins mpa ON mpa.worker_name = wp.display_name
    WHERE wp.auth_uid = auth.uid()
  );
$$;
REVOKE ALL ON FUNCTION public.is_platform_admin() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_platform_admin() TO anon, authenticated, service_role;

-- ── Drop the over-broad anon policies ───────────────────────────────────────
DROP POLICY IF EXISTS "anon read feedback"   ON public.platform_feedback;
DROP POLICY IF EXISTS "anon update feedback" ON public.platform_feedback;
DROP POLICY IF EXISTS "anon delete feedback" ON public.platform_feedback;
DROP POLICY IF EXISTS "anon submit feedback" ON public.platform_feedback;

-- ── Idempotency: drop THIS migration's own policies first so a re-run is clean ─
DROP POLICY IF EXISTS "feedback public reads published" ON public.platform_feedback;
DROP POLICY IF EXISTS "feedback admin reads all"        ON public.platform_feedback;
DROP POLICY IF EXISTS "feedback anon submit"            ON public.platform_feedback;
DROP POLICY IF EXISTS "feedback admin updates"          ON public.platform_feedback;
DROP POLICY IF EXISTS "feedback admin deletes"          ON public.platform_feedback;

-- ── SELECT — public sees only PUBLISHED rows; admins see everything ──────────
CREATE POLICY "feedback public reads published" ON public.platform_feedback
  FOR SELECT TO public
  USING (is_public = true);

CREATE POLICY "feedback admin reads all" ON public.platform_feedback
  FOR SELECT TO public
  USING (public.is_platform_admin());

-- ── INSERT — anyone may submit, but cannot self-publish or pre-triage ───────
-- (defaults — is_public=false, status='new', admin_note=null — satisfy this, so the
--  existing wh-feedback-fab.js widget is unaffected; it never sends these columns.)
CREATE POLICY "feedback anon submit" ON public.platform_feedback
  FOR INSERT TO public
  WITH CHECK (
    is_public IS NOT TRUE
    AND status = 'new'
    AND admin_note IS NULL
    AND resolved_at IS NULL
  );

-- ── UPDATE / DELETE — platform admins only (triage + moderation) ────────────
CREATE POLICY "feedback admin updates" ON public.platform_feedback
  FOR UPDATE TO public
  USING (public.is_platform_admin())
  WITH CHECK (public.is_platform_admin());

CREATE POLICY "feedback admin deletes" ON public.platform_feedback
  FOR DELETE TO public
  USING (public.is_platform_admin());
