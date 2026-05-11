-- voice_journal_entries: durable, per-worker spoken journal with semantic recall.
--
-- This is the canonical archive for the Voice Journal feature. Unlike
-- agent_memory (which has 90-day retention and is gateway-scoped), this
-- table keeps every entry forever and is the source of truth for the
-- journal UI history + semantic similarity search.
--
-- Each row is one journaling exchange:
--   * transcript: the worker's spoken text (Whisper output, hydrated)
--   * reply:      the journal companion's response (hydrated)
--   * lang:       ISO-639-1 / close (e.g. "en", "tl", "ceb")
--   * embedding:  vector(384) over transcript, used for top-K recall
--
-- Privacy boundary: STRICT per-user. RLS keys on auth.uid() = auth_uid
-- only. Even hive members cannot see another worker's journal. The
-- journal is a private diary, not a shared workspace.
--
-- The ai-gateway:
--   1. Embeds the new transcript via _shared/embedding-chain.ts
--   2. Calls search_voice_journal_entries() to retrieve top-K similar
--      past entries for the same worker
--   3. Injects those into the memory block passed to voice-journal-agent
--   4. Persists the new entry (transcript + reply + lang + embedding)
--      via service-role insert after the agent succeeds.

CREATE TABLE IF NOT EXISTS public.voice_journal_entries (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_uid     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  worker_name  text NOT NULL,
  hive_id      uuid REFERENCES public.hives(id) ON DELETE SET NULL,
  transcript   text NOT NULL,
  reply        text,
  lang         text,                                       -- ISO-639-1; nullable when detection failed
  embedding    vector(384),                                -- Voyage/Jina 384-dim, see _shared/embedding-chain.ts
  meta         jsonb DEFAULT '{}'::jsonb,                  -- latency, target_fn, ad-hoc tags
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- Hot path: per-worker chronological list (history feed) -- composite.
CREATE INDEX IF NOT EXISTS idx_voice_journal_auth_created
  ON public.voice_journal_entries (auth_uid, created_at DESC);

-- Semantic recall: ivfflat over the embedding column. lists=50 is a sane
-- default for tables under ~50k rows. Re-tune via REINDEX once volume grows.
CREATE INDEX IF NOT EXISTS idx_voice_journal_embedding
  ON public.voice_journal_entries USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

-- Optional language filter index for "show only Tagalog entries" UI.
CREATE INDEX IF NOT EXISTS idx_voice_journal_auth_lang
  ON public.voice_journal_entries (auth_uid, lang);

ALTER TABLE public.voice_journal_entries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS voice_journal_read   ON public.voice_journal_entries;
DROP POLICY IF EXISTS voice_journal_insert ON public.voice_journal_entries;
DROP POLICY IF EXISTS voice_journal_update ON public.voice_journal_entries;
DROP POLICY IF EXISTS voice_journal_delete ON public.voice_journal_entries;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.voice_journal_entries
  TO anon, authenticated;

-- Read: own rows only. No hive sharing -- this is a private journal.
CREATE POLICY voice_journal_read ON public.voice_journal_entries
  FOR SELECT
  USING (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

-- Insert: only the authenticated worker, only with their own auth_uid.
CREATE POLICY voice_journal_insert ON public.voice_journal_entries
  FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

-- Update: own rows only (e.g. user edits a transcript or deletes an entry's reply).
CREATE POLICY voice_journal_update ON public.voice_journal_entries
  FOR UPDATE
  USING      (auth.uid() IS NOT NULL AND auth.uid() = auth_uid)
  WITH CHECK (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

-- Delete: own rows only.
CREATE POLICY voice_journal_delete ON public.voice_journal_entries
  FOR DELETE
  USING (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

-- ── Semantic recall function ──────────────────────────────────────────────────
-- Returns the top-K most similar past entries for a given worker, by cosine
-- similarity. Called by ai-gateway when routing the voice-journal agent.
--
-- Note: scoped strictly by auth_uid, not hive_id. The journal is private.

CREATE OR REPLACE FUNCTION public.search_voice_journal_entries(
  query_embedding vector(384),
  match_auth_uid  uuid,
  match_count     int DEFAULT 5
)
RETURNS TABLE (
  id           uuid,
  transcript   text,
  reply        text,
  lang         text,
  created_at   timestamptz,
  similarity   float
)
LANGUAGE sql STABLE
SET search_path = public, pg_catalog
AS $$
  -- Per-user scope only. hive_id is intentionally NOT part of the filter:
  -- the voice journal is a private per-worker diary, not a hive-scoped
  -- knowledge surface. Isolation is enforced by auth_uid alignment with
  -- the RLS policies on voice_journal_entries. Other vector search RPCs
  -- (search_calc_knowledge, search_bom_knowledge, etc.) scope by hive_id
  -- because their underlying tables are hive-shared; this one is not.
  SELECT
    vje.id,
    vje.transcript,
    vje.reply,
    vje.lang,
    vje.created_at,
    1 - (vje.embedding <=> query_embedding) AS similarity
  FROM public.voice_journal_entries vje
  WHERE vje.auth_uid = match_auth_uid
    AND vje.embedding IS NOT NULL
  ORDER BY vje.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- The function is invoked from edge functions using the service role,
-- so explicit EXECUTE grants to public roles are not required. Keep
-- the function inaccessible to anon/authenticated to avoid leaking
-- cross-user data via crafted match_auth_uid arguments.
REVOKE ALL ON FUNCTION public.search_voice_journal_entries(vector(384), uuid, int)
  FROM anon, authenticated, public;
GRANT EXECUTE ON FUNCTION public.search_voice_journal_entries(vector(384), uuid, int)
  TO service_role;
