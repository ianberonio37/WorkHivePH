-- ============================================================
-- Platform Feedback / Reviews / Messaging (2026-05-19)
-- ============================================================
-- One inbox for everything a user might want to tell the founder:
--   - reviews (with a 1-5 star rating)
--   - bug reports (with auto-captured page + user-agent)
--   - feature ideas
--   - questions
--   - praise
--   - anything else (kind = 'other')
--
-- Mirrors the polymorphic-table pattern used by mature OSS feedback
-- systems (Fider / LogChimp / Quackback / Astuto): one row per
-- submission with a `kind` discriminator, optional rating, and a
-- triage workflow (new -> triaged -> in_progress -> resolved).
--
-- Identity model: matches the rest of the platform — string-based
-- worker_name + nullable auth_uid (Supabase Auth migration still in
-- progress per platform_admins migration 20260502000006). Anonymous
-- visitors with no session can submit by providing contact_email; the
-- admin can reply via mailto: from the Founder Console.
--
-- Admin gating: marketplace_platform_admins remains the platform-wide
-- admin source of truth. RLS is `USING (true)` per this platform's
-- convention (see community_tables migration) because Auth-derived
-- identity isn't reliable yet; the Founder Console enforces admin-only
-- read/update at the JS layer.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.platform_feedback (
  id            uuid           PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at    timestamptz    NOT NULL    DEFAULT now(),

  -- WHO — every field nullable so anon visitors can submit
  auth_uid      uuid           REFERENCES auth.users(id) ON DELETE SET NULL,
  worker_name   text,
  hive_id       uuid,                       -- not FK'd: public/anon submissions have no hive
  contact_email text,                       -- so admin can reply to anonymous senders

  -- WHAT — polymorphic discriminator + body
  kind          text           NOT NULL    CHECK (kind IN
                  ('bug','idea','question','review','praise','other')),
  rating        smallint                   CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
  subject       text           NOT NULL,
  body          text           NOT NULL,

  -- WHERE — auto-captured by the widget for repro context
  page_url      text,
  user_agent    text,
  screenshot_url text,                      -- optional Supabase Storage URL (Phase 2)

  -- TRIAGE — admin-controlled (Founder Console)
  status        text           NOT NULL    DEFAULT 'new'    CHECK (status IN
                  ('new','triaged','in_progress','resolved','wontfix','duplicate')),
  priority      text                       CHECK (priority IS NULL OR priority IN
                  ('p0','p1','p2','p3')),
  labels        text[]         NOT NULL    DEFAULT '{}',
  admin_note    text,
  resolved_at   timestamptz,

  -- PUBLIC VISIBILITY — Phase 2 toggle so the admin can promote a
  -- submission to a public roadmap page later. Default: private.
  is_public     boolean        NOT NULL    DEFAULT false,
  upvotes       integer        NOT NULL    DEFAULT 0
);

-- Indexes that match the Founder Console query patterns:
--   inbox tabs    -> filter by status
--   per-kind sort -> filter by kind
--   per-hive view -> filter by hive_id
--   timeline      -> order by created_at desc
CREATE INDEX IF NOT EXISTS idx_platform_feedback_status_created
  ON public.platform_feedback (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_platform_feedback_kind_created
  ON public.platform_feedback (kind, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_platform_feedback_hive_created
  ON public.platform_feedback (hive_id, created_at DESC)
  WHERE hive_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_platform_feedback_public_upvotes
  ON public.platform_feedback (upvotes DESC, created_at DESC)
  WHERE is_public = true;

-- ── RLS ────────────────────────────────────────────────────────────────────
-- Per this platform's convention (see community_tables): RLS is open at the
-- DB layer (USING true) because Auth-derived identity isn't reliable yet,
-- with role enforcement at the JS layer (Founder Console checks
-- marketplace_platform_admins before exposing the inbox).
--
-- Threat model:
--   Spam submissions     -> rate-limit trigger below
--   Stale data reads     -> Founder Console is admin-gated client-side
--   Cross-tenant leakage -> N/A: feedback is platform-wide, not hive-scoped

ALTER TABLE public.platform_feedback ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.platform_feedback
  TO anon, authenticated;

DROP POLICY IF EXISTS "anon submit feedback"   ON public.platform_feedback;
DROP POLICY IF EXISTS "anon read feedback"     ON public.platform_feedback;
DROP POLICY IF EXISTS "anon update feedback"   ON public.platform_feedback;
DROP POLICY IF EXISTS "anon delete feedback"   ON public.platform_feedback;

CREATE POLICY "anon submit feedback"
  ON public.platform_feedback FOR INSERT WITH CHECK (true);

-- Open read so the Founder Console (signed-in admin) AND a future public
-- /feedback/ roadmap page (showing is_public=true items) can both query
-- without auth context. Admin gating happens in JS.
CREATE POLICY "anon read feedback"
  ON public.platform_feedback FOR SELECT USING (true);

CREATE POLICY "anon update feedback"
  ON public.platform_feedback FOR UPDATE USING (true);

CREATE POLICY "anon delete feedback"
  ON public.platform_feedback FOR DELETE USING (true);


-- ── Rate-limit trigger ─────────────────────────────────────────────────────
-- Prevents accidental form-spam (e.g. user hits Send 10× during a network
-- hiccup) and rudimentary bot spray. Limit: 5 submissions per identity per
-- hour, where identity is (in order of preference):
--   1. auth_uid  (signed-in user)
--   2. worker_name (legacy string identity)
--   3. contact_email (anon submitter who provided an email)
-- Pure-anonymous with no email: 5 submissions per hour from anyone with no
-- identity bucket. Crude but kills the obvious abuse vector.

CREATE OR REPLACE FUNCTION public.check_platform_feedback_rate_limit()
  RETURNS trigger
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = pg_catalog, public
AS $$
DECLARE
  v_recent_count integer;
  v_identity     text;
BEGIN
  v_identity := COALESCE(
    NEW.auth_uid::text,
    NEW.worker_name,
    NEW.contact_email,
    'anonymous'
  );

  SELECT COUNT(*) INTO v_recent_count
  FROM public.platform_feedback
  WHERE created_at > now() - interval '1 hour'
    AND COALESCE(
      auth_uid::text, worker_name, contact_email, 'anonymous'
    ) = v_identity;

  IF v_recent_count >= 5 THEN
    RAISE EXCEPTION 'Feedback rate limit reached: max 5 submissions per hour per identity (%). Try again later.', v_identity
      USING ERRCODE = '23P01';   -- exclusion_violation; client can show friendly toast
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_platform_feedback_rate_limit ON public.platform_feedback;
CREATE TRIGGER trg_platform_feedback_rate_limit
  BEFORE INSERT ON public.platform_feedback
  FOR EACH ROW EXECUTE FUNCTION public.check_platform_feedback_rate_limit();


-- ── resolved_at auto-stamp ─────────────────────────────────────────────────
-- Whenever status flips to resolved/wontfix/duplicate, set resolved_at if
-- not already set. Lets the Founder Console show "resolved 3d ago" cleanly.

CREATE OR REPLACE FUNCTION public.platform_feedback_stamp_resolved()
  RETURNS trigger
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = pg_catalog, public
AS $$
BEGIN
  IF NEW.status IN ('resolved','wontfix','duplicate')
     AND OLD.status NOT IN ('resolved','wontfix','duplicate')
     AND NEW.resolved_at IS NULL THEN
    NEW.resolved_at := now();
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_platform_feedback_stamp_resolved
  ON public.platform_feedback;
CREATE TRIGGER trg_platform_feedback_stamp_resolved
  BEFORE UPDATE OF status ON public.platform_feedback
  FOR EACH ROW EXECUTE FUNCTION public.platform_feedback_stamp_resolved();


-- ── Documentation ──────────────────────────────────────────────────────────
COMMENT ON TABLE public.platform_feedback IS
  'Universal feedback inbox: reviews, bugs, ideas, questions, praise, other.
   Polymorphic table — `kind` discriminator + optional `rating` for reviews.
   Accepts anon submissions; admin triage in Founder Console (sec-feel section).';

COMMENT ON COLUMN public.platform_feedback.kind IS
  'Discriminator: bug | idea | question | review | praise | other.
   Drives form fields in wh-feedback-fab.js and grouping in the admin inbox.';

COMMENT ON COLUMN public.platform_feedback.status IS
  'Triage workflow: new -> triaged -> in_progress -> resolved | wontfix | duplicate.
   `resolved_at` auto-stamps on transition into a terminal state.';

COMMENT ON COLUMN public.platform_feedback.is_public IS
  'Phase 2 — admin promotes an item to a public /feedback/ roadmap page.
   Default false so private submissions stay private.';

COMMENT ON FUNCTION public.check_platform_feedback_rate_limit() IS
  'BEFORE INSERT trigger. Caps 5 submissions/hour per identity bucket
   (auth_uid > worker_name > contact_email > "anonymous"). Raises 23P01
   so the widget can show a friendly retry toast.';
