-- 20260731000002_embedding_outbox_spine.sql
--
-- AUTO-EMBED P1 — the indexing contract's spine (AUTO_EMBED_INFRASTRUCTURE_PLAN.md).
--
-- Ian, 2026-07-31: "anything they put inside their account should have an auto embedder."
-- Locked with him: visibility MIRRORS THE SOURCE ROW; scope is everything, phased. This is P1: the outbox,
-- the registry, and the generic trigger, wired on `logbook` only.
--
-- WHAT THIS REPLACES AND WHY. Today three dashboard-created webhooks fire HTTP *directly from a trigger*
-- (`supabase_functions.http_request`) into `embed-entry`. Measured 2026-07-31, that shape fails four ways:
--   SILENT      fire-and-forget from a trigger has no retry and no backpressure; a 500 sat in
--               net._http_response and nothing noticed. Result: 3,811 logbook rows, 533 retrievable (14%).
--   UNSAFE      the URL *and a service-role bearer* are baked into the trigger body, which is how LOCAL
--               writes reached PRODUCTION (see the gate local-triggers-dont-call-prod).
--   UNSCALABLE  every surface needs a new dashboard hook AND a new branch in the function; four user
--               surfaces (voice journal, community posts, progress logs, change orders) never got one.
--   UNMEASURED  nothing asked "what fraction is retrievable?", so ~9% platform-wide looked like success.
--
-- THE PRECEDENT THAT MAKES THIS THE RIGHT PATTERN HERE. SERVICE_HAILING_ROADMAP §4b evaluated the
-- transactional outbox for the `service_*` triggers and correctly DECLINED it: those write only to this DB
-- in the SAME transaction, so an outbox would ADD an inconsistency window. Its discriminating test was
-- `prosrc !~ http_request|pg_net|net.http` — and the embed triggers are exactly the case that test was built
-- to find. Same platform, opposite verdict, because the premise differs.
--
-- THE SHAPE: the trigger writes ONE row and does nothing else — no network, no secret, and it ROLLS BACK
-- WITH THE USER'S TRANSACTION, so a failed write can never leave a phantom index entry. A relay claims
-- batches with FOR UPDATE SKIP LOCKED (substrate/external/external-postgres-skip-locked-job-queue-*),
-- embeds them in batches, and retries with backoff before dead-lettering.
--
-- ⚠ DEPLOY ORDER (Ian's gate). This migration DROPS the old fire-and-forget trigger and replaces it with the
-- outbox trigger. Applying it to PRODUCTION without the relay running there would stop production embedding
-- until the relay is deployed — so deploy the relay first, or accept a pause. Locally the old trigger is
-- already DISABLED, so nothing changes for us but the enqueue.

BEGIN;

-- ── the outbox ─────────────────────────────────────────────────────────────────────────────────────────
-- `row_id` is TEXT on purpose: logbook.id is text while most tables use uuid, and one generic queue must
-- carry both. The relay resolves the row through the registry's source_table, so the type never matters here.
CREATE TABLE IF NOT EXISTS public.embedding_outbox (
  id              bigserial PRIMARY KEY,
  source_table    text        NOT NULL,
  row_id          text        NOT NULL,
  hive_id         uuid,
  auth_uid        uuid,
  op              text        NOT NULL DEFAULT 'INSERT',
  enqueued_at     timestamptz NOT NULL DEFAULT now(),
  attempts        integer     NOT NULL DEFAULT 0,
  next_attempt_at timestamptz NOT NULL DEFAULT now(),
  claimed_at      timestamptz,
  done_at         timestamptz,
  last_error      text
);

-- One PENDING job per row. An edit while a job is still queued collapses into that job rather than adding a
-- second — the re-embed replaces by conflict_key anyway, so two jobs would buy nothing and cost a call.
CREATE UNIQUE INDEX IF NOT EXISTS embedding_outbox_one_pending_per_row
  ON public.embedding_outbox (source_table, row_id) WHERE done_at IS NULL;

-- The claim query's index: due, unfinished, oldest first.
CREATE INDEX IF NOT EXISTS embedding_outbox_claimable
  ON public.embedding_outbox (next_attempt_at, id) WHERE done_at IS NULL;

-- ── the registry ───────────────────────────────────────────────────────────────────────────────────────
-- A row per embeddable surface, so adding one is CONFIG plus a two-line trigger rather than a new branch in
-- an edge function. `text_fields` is ordered [{col,label}] and reproduces exactly what embed-entry composes,
-- which is also what the retrievability gate must count against — one definition, not three.
CREATE TABLE IF NOT EXISTS public.embedding_registry (
  source_table    text PRIMARY KEY,
  target_table    text        NOT NULL,
  conflict_key    text        NOT NULL,
  min_chars       integer     NOT NULL DEFAULT 50,
  -- The embedding model is a property of the CORPUS, pinned and never inferred: a blind failover chain that
  -- switches provider switches VECTOR SPACE, and cosine becomes noise with no error raised. Pinned here so
  -- ingest and query cannot drift apart.
  embedding_model text        NOT NULL,
  text_fields     jsonb       NOT NULL,
  -- 'mirror_source' = findable by exactly whoever could already see the original row (Ian's decision).
  -- Indexing must never widen who can see something.
  visibility      text        NOT NULL DEFAULT 'mirror_source'
                  CHECK (visibility IN ('mirror_source','author_only','hive_wide')),
  active          boolean     NOT NULL DEFAULT true,
  created_at      timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.embedding_registry
  (source_table, target_table, conflict_key, min_chars, embedding_model, text_fields, visibility)
VALUES
  ('logbook', 'fault_knowledge', 'logbook_id', 50, 'bge-small-en-v1.5',
   '[{"col":"machine","label":"Equipment"},{"col":"problem","label":"Problem"},
     {"col":"root_cause","label":"Root cause"},{"col":"action","label":"Action taken"},
     {"col":"knowledge","label":"Lesson learned"},{"col":"category","label":"Category"}]'::jsonb,
   'mirror_source')
ON CONFLICT (source_table) DO NOTHING;

-- ── the generic enqueue trigger ────────────────────────────────────────────────────────────────────────
-- Deliberately tiny: registry lookup, one INSERT, return. No network call, no secret, nothing that can fail
-- slowly. to_jsonb(NEW) keeps it table-agnostic so every future surface reuses this exact function.
CREATE OR REPLACE FUNCTION public.enqueue_for_embedding()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
DECLARE
  j       jsonb;
  v_hive  uuid;
  v_auth  uuid;
  v_id    text;
BEGIN
  -- An inactive or unregistered surface enqueues nothing, so a trigger can be attached ahead of the config
  -- and switched on by flipping `active` — no DDL to enable a surface.
  IF NOT EXISTS (SELECT 1 FROM public.embedding_registry r
                  WHERE r.source_table = TG_TABLE_NAME AND r.active) THEN
    RETURN NULL;
  END IF;

  j    := to_jsonb(NEW);
  v_id := j->>'id';
  IF v_id IS NULL THEN
    RETURN NULL;                       -- nothing addressable to re-read later
  END IF;

  -- These columns are absent on some surfaces; a missing key yields NULL rather than an error, which is why
  -- the cast is guarded instead of assumed.
  BEGIN v_hive := nullif(j->>'hive_id','')::uuid;  EXCEPTION WHEN others THEN v_hive := NULL; END;
  BEGIN v_auth := nullif(j->>'auth_uid','')::uuid; EXCEPTION WHEN others THEN v_auth := NULL; END;

  INSERT INTO public.embedding_outbox (source_table, row_id, hive_id, auth_uid, op)
  VALUES (TG_TABLE_NAME, v_id, v_hive, v_auth, TG_OP)
  ON CONFLICT (source_table, row_id) WHERE done_at IS NULL
  DO UPDATE SET enqueued_at     = now(),
                op              = EXCLUDED.op,
                attempts        = 0,
                next_attempt_at = now(),
                last_error      = NULL;
  RETURN NULL;                          -- AFTER trigger: the return value is ignored
END
$fn$;

COMMENT ON FUNCTION public.enqueue_for_embedding() IS
  'Auto-embed spine: enqueues a row for embedding in the SAME transaction as the write. No network, no '
  'secrets, and it rolls back with the user''s transaction. Registry-driven, so every surface reuses it.';

-- ── wire logbook (P1), replacing the fire-and-forget webhook ───────────────────────────────────────────
DROP TRIGGER IF EXISTS "embed-logbook" ON public.logbook;
DROP TRIGGER IF EXISTS trg_embed_outbox_logbook ON public.logbook;
CREATE TRIGGER trg_embed_outbox_logbook
  AFTER INSERT OR UPDATE ON public.logbook
  FOR EACH ROW EXECUTE FUNCTION public.enqueue_for_embedding();

-- ── lock the queue down ────────────────────────────────────────────────────────────────────────────────
-- Neither table is user-facing. RLS on with NO policy means authenticated/anon read and write nothing, while
-- the relay (service-role) bypasses RLS. The explicit REVOKE matters as much as the RLS: a lingering table
-- GRANT is how anon-destroyable rows have appeared here before.
ALTER TABLE public.embedding_outbox   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.embedding_registry ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.embedding_outbox   FROM anon, authenticated;
REVOKE ALL ON public.embedding_registry FROM anon, authenticated;

COMMIT;
