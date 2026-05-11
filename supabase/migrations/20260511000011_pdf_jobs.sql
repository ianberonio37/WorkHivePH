-- pdf_jobs -- ingestion-state table for the PDF -> knowledge pipeline.
--
-- Each row is one PDF being ingested. The pdf-ingest edge fn polls the
-- table for status='pending', chunks the document, embeds each chunk
-- via _shared/embedding-chain, and inserts into the matching *_knowledge
-- table. Status transitions: pending -> processing -> done / failed.
--
-- Closes Phase 1.1 of the RAG roadmap. PDF text extraction happens
-- client-side (browser PDF.js) and is uploaded as pre-chunked text in
-- the `chunks_json` column to keep the edge fn light and Deno-friendly.

CREATE TABLE IF NOT EXISTS public.pdf_jobs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id         uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  uploaded_by     text,                                              -- worker_name who uploaded
  source_name     text NOT NULL,                                     -- e.g. "Grundfos CR-15 Manual.pdf"
  source_url      text,                                              -- Supabase Storage path (optional)
  target_table    text NOT NULL CHECK (target_table IN (
                    'fault_knowledge', 'pm_knowledge', 'bom_knowledge',
                    'project_knowledge', 'skill_knowledge', 'calc_knowledge'
                  )),
  chunks_json     jsonb,                                             -- [{text, meta}, ...] pre-extracted
  total_chunks    integer,
  embedded_chunks integer NOT NULL DEFAULT 0,
  status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'done', 'failed')),
  error_message   text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  started_at      timestamptz,
  finished_at     timestamptz
);

CREATE INDEX IF NOT EXISTS idx_pdf_jobs_status_created
  ON public.pdf_jobs (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pdf_jobs_hive_created
  ON public.pdf_jobs (hive_id, created_at DESC);

GRANT SELECT, INSERT, UPDATE ON public.pdf_jobs TO anon, authenticated;

ALTER TABLE public.pdf_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS pdf_jobs_read   ON public.pdf_jobs;
DROP POLICY IF EXISTS pdf_jobs_insert ON public.pdf_jobs;
DROP POLICY IF EXISTS pdf_jobs_update ON public.pdf_jobs;

-- Read: hive members can see jobs scoped to their hive.
CREATE POLICY pdf_jobs_read ON public.pdf_jobs
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND hive_id IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = pdf_jobs.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Insert: any authenticated user can submit a job for their own hive.
CREATE POLICY pdf_jobs_insert ON public.pdf_jobs
  FOR INSERT WITH CHECK (
    auth.uid() IS NOT NULL
    AND hive_id IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = pdf_jobs.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Update: only the edge fn (service role) writes status transitions.
-- Anon/auth users cannot modify in-flight jobs.
CREATE POLICY pdf_jobs_update ON public.pdf_jobs
  FOR UPDATE USING (false);
