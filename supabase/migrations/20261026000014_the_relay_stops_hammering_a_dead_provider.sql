-- 20261026000014_the_relay_stops_hammering_a_dead_provider.sql
--
-- THE RELAY KEPT SENDING 20 JOBS A MINUTE INTO AN EMBEDDER THAT WAS DOWN (BRH-AC, 2026-10-26). Measured on the local stack
-- the same day: the embed server had been killed four days earlier, and the in-database relay (20261026000006) sent
-- its batch every minute regardless - 982 failed embed calls in one hour, 546 edge-runtime WORKER_LIMIT refusals, and
-- 1,600 model-call ledger rows saying "threw". 20261026000011 stopped such jobs from dead-lettering; it did not stop
-- the relay from asking. Production met the same shape that morning, when Gemini's daily allowance ran out.
--
-- A circuit breaker: when the last ten minutes hold five or more provider-unavailable failures and no success, the
-- relay sends ONE job a tick - a probe - instead of its batch. The first success closes the breaker and the full batch
-- resumes on the next tick. Each failed settle now stamps failed_at, which is what the breaker counts.

ALTER TABLE public.embedding_outbox ADD COLUMN IF NOT EXISTS failed_at timestamptz;

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
  v_wait   boolean;
  v_limit  integer;
  v_n      integer;
  v_batch  integer := greatest(1, least(p_batch, 100));
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
      -- the provider is unavailable (not this request's fault): wait it out
      v_wait := r.unanswered OR r.timed_out OR coalesce(r.status_code, 0) = 429 OR coalesce(r.status_code, 0) >= 500
                OR v_err ILIKE '%embedding providers failed%' OR v_err ILIKE '%quota%' OR v_err ILIKE '%rate limit%';
      v_limit := CASE WHEN v_wait THEN 48 ELSE 5 END;
      UPDATE public.embedding_outbox
         SET request_id = NULL,
             claimed_at = NULL,
             done_at = CASE WHEN attempts >= v_limit THEN now() END,
             last_error = CASE WHEN attempts >= v_limit THEN 'DEAD after ' || v_limit || ' attempts: ' ELSE '' END || left(v_err, 300),
             next_attempt_at = now() + least(30 * power(2, greatest(attempts - 1, 0)), 3600) * interval '1 second',
             failed_at = now()
       WHERE id = r.id;
      IF r.attempts >= v_limit THEN n_dead := n_dead + 1; ELSE n_retry := n_retry + 1; END IF;
    END IF;
  END LOOP;

  -- 2. SWEEP orphans: a queued row whose source is gone (or in the trash) has nothing to index
  FOR r IN SELECT DISTINCT g.source_table FROM public.embedding_registry g WHERE g.active LOOP
    EXECUTE format(
      'UPDATE public.embedding_outbox o
          SET done_at = now(), last_error = ''source row deleted after enqueue - nothing left to embed''
        WHERE o.done_at IS NULL AND o.request_id IS NULL AND o.source_table = %L
          AND NOT EXISTS (SELECT 1 FROM public.%I l WHERE l.id::text = o.row_id
                             AND nullif(to_jsonb(l) ->> ''deleted_at'', '''') IS NULL)',
      r.source_table, r.source_table);
    GET DIAGNOSTICS v_n = ROW_COUNT;
    n_orphan := n_orphan + v_n;
  END LOOP;

  -- 3. THE BREAKER: a provider that has failed five times in ten minutes with no success gets one probe a tick
  IF (SELECT count(*) FROM public.embedding_outbox
       WHERE failed_at > now() - interval '10 minutes'
         AND (last_error ILIKE '%embedding providers failed%' OR last_error ILIKE '%quota%' OR last_error ILIKE '%rate limit%'
              OR last_error ILIKE '5__ %' OR last_error ILIKE '429 %' OR last_error ILIKE 'no answer%' OR last_error ILIKE '%timed out%'
              OR last_error ILIKE '%WORKER_LIMIT%')) >= 5
     AND NOT EXISTS (SELECT 1 FROM public.embedding_outbox
                      WHERE done_at > now() - interval '10 minutes' AND last_error IS NULL) THEN
    v_batch := 1;
  END IF;

  -- 4. CLAIM due jobs and SEND them
  FOR r IN
    WITH due AS (
      SELECT o.id FROM public.embedding_outbox o
       WHERE o.done_at IS NULL AND o.request_id IS NULL
         AND o.next_attempt_at <= now()
         AND (o.claimed_at IS NULL OR o.claimed_at < now() - interval '300 seconds')
         AND EXISTS (SELECT 1 FROM public.embedding_registry g WHERE g.source_table = o.source_table AND g.active)
       ORDER BY o.id
       FOR UPDATE SKIP LOCKED
       LIMIT v_batch)
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

  RETURN jsonb_build_object('sent', n_sent, 'done', n_done, 'retry', n_retry, 'dead', n_dead, 'orphaned', n_orphan,
                            'breaker_open', v_batch = 1 AND p_batch > 1);
END
$$;

REVOKE ALL ON FUNCTION private.relay_embedding_outbox(integer) FROM PUBLIC, anon, authenticated;
