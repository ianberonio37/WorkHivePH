-- resume_documents + resume_versions: per-worker Resume / CV Builder store.
--
-- The Resume / CV Builder (resume.html) lets a Filipino industrial worker turn
-- the experience they already have in WorkHive (Skill Matrix, Logbook, badges,
-- profile) PLUS files they upload from a phone (photo / PDF / Word / Excel)
-- into a professional, exportable resume. The working resume is stored here as
-- a JSON Resume object (https://jsonresume.org/schema, v1.0.0) so it renders to
-- ATS-plain HTML, a designed template, PDF, and a portable .json export.
--
-- Privacy boundary: STRICT per-user, exactly like voice_journal_entries. A
-- resume is a private personal document, NOT a hive-shared surface. RLS keys on
-- auth.uid() = auth_uid only. hive_id is stored for CONTEXT (which plant the
-- worker is currently in, used to label auto-filled experience) but is NOT part
-- of the access predicate -- even hive supervisors cannot read a member's resume.
--
-- Uploaded source files are process-and-discard by default (extract -> JSON ->
-- discard) for the privacy of vulnerable users; only the extracted JSON lives
-- here. A private resume-uploads Storage bucket is added in a later phase for
-- the explicit "keep a copy" opt-in.
--
-- Skills consulted:
--   multitenant-engineer (owner-only RLS, auth.uid() predicate, no hive sharing)
--   architect (jsonb document store + version snapshots for undo / internal control)
--   data-engineer (composite hot-path index, touch trigger for updated_at)
--   security (no service-role-only leak path; owner-scoped GRANTs)

BEGIN;

-- ── resume_documents: one row per saved resume (v1 UI uses a single working
--    resume per worker, but multiple are allowed for job-tailored variants). ──
CREATE TABLE IF NOT EXISTS public.resume_documents (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_uid     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  worker_name  text NOT NULL,
  hive_id      uuid REFERENCES public.hives(id) ON DELETE SET NULL,  -- context only, NOT an access key
  title        text NOT NULL DEFAULT 'My Resume',                    -- user-facing label for the variant
  doc          jsonb NOT NULL DEFAULT '{}'::jsonb,                    -- the JSON Resume object
  template     text NOT NULL DEFAULT 'ats-plain',                     -- 'ats-plain' | 'workhive'
  updated_at   timestamptz NOT NULL DEFAULT now(),
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- Hot path: a worker's resume list, newest first.
CREATE INDEX IF NOT EXISTS idx_resume_documents_auth_updated
  ON public.resume_documents (auth_uid, updated_at DESC);

-- ── resume_versions: cheap jsonb snapshots for undo / "internal control". The
--    client snapshots before each AI merge or destructive edit and prunes to
--    the most recent ~10 per resume. ──
CREATE TABLE IF NOT EXISTS public.resume_versions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resume_id    uuid NOT NULL REFERENCES public.resume_documents(id) ON DELETE CASCADE,
  auth_uid     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,  -- denormalized for a simple RLS predicate
  doc          jsonb NOT NULL,
  note         text,                                                        -- e.g. 'before AI polish', 'before merge from upload'
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_resume_versions_resume_created
  ON public.resume_versions (resume_id, created_at DESC);

-- ── updated_at touch trigger (canonical recipe; mirrors logbook_updated_at) ──
CREATE OR REPLACE FUNCTION public.resume_documents_touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_catalog
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_resume_documents_touch ON public.resume_documents;
CREATE TRIGGER trg_resume_documents_touch
  BEFORE UPDATE ON public.resume_documents
  FOR EACH ROW
  EXECUTE FUNCTION public.resume_documents_touch_updated_at();

-- ── RLS: owner-only on both tables (private personal document) ───────────────
ALTER TABLE public.resume_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resume_versions  ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.resume_documents TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.resume_versions  TO anon, authenticated;

-- resume_documents: own rows only, all four verbs.
DROP POLICY IF EXISTS resume_documents_read   ON public.resume_documents;
DROP POLICY IF EXISTS resume_documents_insert ON public.resume_documents;
DROP POLICY IF EXISTS resume_documents_update ON public.resume_documents;
DROP POLICY IF EXISTS resume_documents_delete ON public.resume_documents;

CREATE POLICY resume_documents_read ON public.resume_documents
  FOR SELECT
  USING (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

CREATE POLICY resume_documents_insert ON public.resume_documents
  FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

CREATE POLICY resume_documents_update ON public.resume_documents
  FOR UPDATE
  USING      (auth.uid() IS NOT NULL AND auth.uid() = auth_uid)
  WITH CHECK (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

CREATE POLICY resume_documents_delete ON public.resume_documents
  FOR DELETE
  USING (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

-- resume_versions: own rows only. A version is readable/writable only by the
-- worker who owns it; the FK to resume_documents adds defense in depth.
DROP POLICY IF EXISTS resume_versions_read   ON public.resume_versions;
DROP POLICY IF EXISTS resume_versions_insert ON public.resume_versions;
DROP POLICY IF EXISTS resume_versions_delete ON public.resume_versions;

CREATE POLICY resume_versions_read ON public.resume_versions
  FOR SELECT
  USING (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

CREATE POLICY resume_versions_insert ON public.resume_versions
  FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

-- Versions are immutable history; allow delete (for client-side pruning) but no update.
CREATE POLICY resume_versions_delete ON public.resume_versions
  FOR DELETE
  USING (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

COMMENT ON TABLE public.resume_documents IS
  'Per-worker Resume / CV Builder document (JSON Resume schema in doc jsonb). Private: RLS owner-only via auth.uid()=auth_uid. hive_id is context, not an access key.';
COMMENT ON TABLE public.resume_versions IS
  'Undo snapshots for resume_documents. Owner-only RLS. Client prunes to ~10 most recent per resume.';

COMMIT;
