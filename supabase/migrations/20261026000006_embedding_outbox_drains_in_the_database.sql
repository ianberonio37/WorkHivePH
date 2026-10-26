-- 20261026000006_embedding_outbox_drains_in_the_database.sql
--
-- PRODUCTION'S EMBEDDING OUTBOX HAD NO RELAY (BRH-AC, 2026-10-26). The outbox spine (20260731000002) moved every
-- embedding off the triggers and into embedding_outbox, drained by tools/drain_embedding_outbox.py - a host process
-- that reads the local database through docker and calls the local embedder. Its own header said it: "applying it to
-- PRODUCTION without the relay running there would stop production embedding". That is what happened. Read on
-- production 2026-10-26: 86 jobs queued since 2026-08-10 (52 logbook entries, 34 PM completions), attempts 0 on every
-- one - nothing a person wrote there since August reached fault_knowledge or pm_knowledge, so the assistant could not
-- find any of it.
--
-- The relay now lives where the queue lives. pg_cron runs private.relay_embedding_outbox() every minute:
--   1. SETTLE - a job whose embed-entry call has answered (net._http_response) is done on a 2xx; anything else backs
--      off 30s, 1m, 2m, 4m... and dead-letters after 5 attempts, keeping its error (the Python relay's rules). A call
--      with no answer after 10 minutes is treated as failed, so a lost response cannot strand a job.
--   2. CLAIM + SEND - due jobs are claimed with FOR UPDATE SKIP LOCKED and a 5-minute lease (two relays, or this and the
--      Python relay locally, never take the same row), the source row is read, and it is posted to embed-entry in the
--      database-webhook shape that function was written for. A row deleted after it was queued is closed as an orphan.
-- Only a source table the embedding registry lists (active) is ever read, so the outbox cannot name an arbitrary table.
-- The endpoint and bearer come from private.wh_setting (20261026000005): production reads them from Vault; a database
-- with neither (local, CI) returns {"skipped": ...} and the Python relay keeps draining there.

ALTER TABLE public.embedding_outbox ADD COLUMN IF NOT EXISTS request_id bigint;

CREATE OR REPLACE FUNCTION private.relay_embedding_outbox(p_batch integer DEFAULT 20)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, private, pg_temp
AS $$
DECLARE
  v_url    text := private.wh_setting('supabase_functions_url');
  v_key    text := private.wh_setting('service_role_key');
  r        record;
  v_rec    jsonb;
  v_req    bigint;
  v_ok     boolean;
  v_err    text;
  n_sent   integer := 0;
  n_done   integer := 0;
  n_retry  integer := 0;
  n_dead   integer := 0;
  n_orphan integer := 0;
BEGIN
  IF coalesce(v_url, '') = '' OR coalesce(v_key, '') = '' THEN
    RETURN jsonb_build_object('skipped', 'no functions endpoint or bearer in this database');
  END IF;

  -- 1. SETTLE the calls sent on earlier ticks
  FOR r IN
    SELECT o.id, o.attempts, h.status_code, h.timed_out, h.error_msg, left(h.content, 300) AS content,
           (h.id IS NULL) AS unanswered
      FROM public.embedding_outbox o
      LEFT JOIN net._http_response h ON h.id = o.request_id
     WHERE o.done_at IS NULL AND o.request_id IS NOT NULL
       AND (h.id IS NOT NULL OR o.claimed_at < now() - interval '10 minutes')
  LOOP
    v_ok := NOT r.unanswered AND r.status_code BETWEEN 200 AND 299;
    IF v_ok THEN
      UPDATE public.embedding_outbox SET done_at = now(), last_error = NULL, request_id = NULL WHERE id = r.id;
      n_done := n_done + 1;
    ELSE
      v_err := CASE WHEN r.unanswered THEN 'no answer from embed-entry within 10 minutes'
                    WHEN r.timed_out THEN 'embed-entry timed out'
                    ELSE coalesce(r.status_code::text, '?') || ' ' || coalesce(r.error_msg, r.content, '') END;
      UPDATE public.embedding_outbox
         SET request_id = NULL,
             claimed_at = NULL,
             done_at = CASE WHEN attempts >= 5 THEN now() END,
             last_error = CASE WHEN attempts >= 5 THEN 'DEAD after 5 attempts: ' ELSE '' END || left(v_err, 300),
             next_attempt_at = now() + (30 * power(2, greatest(attempts - 1, 0))) * interval '1 second'
       WHERE id = r.id;
      IF r.attempts >= 5 THEN n_dead := n_dead + 1; ELSE n_retry := n_retry + 1; END IF;
    END IF;
  END LOOP;

  -- 2. CLAIM due jobs and SEND them
  FOR r IN
    WITH due AS (
      SELECT o.id FROM public.embedding_outbox o
       WHERE o.done_at IS NULL AND o.request_id IS NULL
         AND o.next_attempt_at <= now()
         AND (o.claimed_at IS NULL OR o.claimed_at < now() - interval '300 seconds')
         AND EXISTS (SELECT 1 FROM public.embedding_registry g WHERE g.source_table = o.source_table AND g.active)
       ORDER BY o.id
       FOR UPDATE SKIP LOCKED
       LIMIT greatest(1, least(p_batch, 100)))
    UPDATE public.embedding_outbox o
       SET claimed_at = now(), attempts = o.attempts + 1
      FROM due
     WHERE o.id = due.id
    RETURNING o.id, o.source_table, o.row_id
  LOOP
    EXECUTE format('SELECT to_jsonb(l) FROM public.%I l WHERE l.id::text = $1 '
                   'AND nullif(to_jsonb(l) ->> ''deleted_at'', '''') IS NULL', r.source_table)
       INTO v_rec USING r.row_id;
    IF v_rec IS NULL THEN
      -- D3: a row deleted after it was queued has nothing to index; retrying it only delays the live rows behind it
      UPDATE public.embedding_outbox
         SET done_at = now(), last_error = 'source row deleted after enqueue - nothing left to embed'
       WHERE id = r.id;
      n_orphan := n_orphan + 1;
      CONTINUE;
    END IF;
    SELECT net.http_post(
             url := v_url || '/embed-entry',
             body := jsonb_build_object('type', 'INSERT', 'table', r.source_table, 'record', v_rec),
             headers := jsonb_build_object('Content-Type', 'application/json', 'Authorization', 'Bearer ' || v_key),
             timeout_milliseconds := 30000)
      INTO v_req;
    UPDATE public.embedding_outbox SET request_id = v_req WHERE id = r.id;
    n_sent := n_sent + 1;
  END LOOP;

  RETURN jsonb_build_object('sent', n_sent, 'done', n_done, 'retry', n_retry, 'dead', n_dead, 'orphaned', n_orphan);
END
$$;

REVOKE ALL ON FUNCTION private.relay_embedding_outbox(integer) FROM PUBLIC, anon, authenticated;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.unschedule(jobid) FROM cron.job WHERE jobname = 'embedding-outbox-relay';
    PERFORM cron.schedule('embedding-outbox-relay', '* * * * *', 'SELECT private.relay_embedding_outbox(20);');
  END IF;
END
$$;
