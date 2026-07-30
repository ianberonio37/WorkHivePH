-- =====================================================================
-- C12 · DURABLE SIDE-EFFECTS — the outbox, and the delivery that never happened
-- =====================================================================
-- WHY THIS EXISTS, precisely (the premise was checked before it was built — see roadmap §4b.6):
--
--   The DB triggers on service_requests (land_accepted_job_on_dayplan, mint_settlement_commission,
--   writeback_service_job_to_logbook, sync_provider_availability, journal_service_request) write ONLY
--   to this database inside the SAME transaction. A failure rolls the whole transition back. That is
--   already atomic and is strictly BETTER than an outbox — they are deliberately NOT touched here.
--
--   The one effect on this arc that genuinely crosses a boundary is WEB PUSH, and it was built but
--   NEVER SENT: push_subscriptions exists, sw.js handles `push`, VAPID is configured, and
--   marketplace-seller.html subscribes providers — but a repo-wide search finds NO caller of
--   `notify-push` anywhere. Its own docstring admitted it: "Callers are backend: the broadcast fan-out
--   (DB webhook/cron, future)". A provider granted permission, subscribed, and received nothing —
--   exactly the failure G3 existed to prevent ("without this, hailing fails on mobile").
--
-- So the outbox is not a retrofit of correct triggers; it is the delivery spine for boundary-crossing
-- effects, and its first consumer is the push fan-out that is missing today. Enqueue happens in the
-- SAME transaction as the transition (a plain INSERT) — that is precisely what makes it correct: the
-- intent to notify commits if and only if the state change does. Delivery is then retried by a relay
-- until it succeeds or dead-letters, so a dead consumer can never silently swallow a job offer.
--
-- Everything is inside Postgres: no broker, no new dependency (pg_cron + pg_net are already installed
-- and 5 existing jobs already use exactly this net.http_post + GUC recipe).

BEGIN;

CREATE TABLE IF NOT EXISTS public.service_outbox (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  consumer        text        NOT NULL,                      -- e.g. 'notify-push'
  payload         jsonb       NOT NULL,
  status          text        NOT NULL DEFAULT 'pending',    -- pending | in_flight | done | dead
  attempts        int         NOT NULL DEFAULT 0,
  max_attempts    int         NOT NULL DEFAULT 6,
  next_attempt_at timestamptz NOT NULL DEFAULT now(),
  request_id      bigint,                                    -- pg_net id while in_flight
  last_error      text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT service_outbox_status_chk CHECK (status IN ('pending','in_flight','done','dead'))
);

-- The claim query's index: only rows that are actually claimable.
CREATE INDEX IF NOT EXISTS service_outbox_claimable_idx
  ON public.service_outbox (next_attempt_at, created_at)
  WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS service_outbox_inflight_idx
  ON public.service_outbox (request_id)
  WHERE status = 'in_flight';

-- Infrastructure, not user data: RLS on with NO client policy at all. Nothing outside the
-- SECURITY DEFINER helpers below may read or write it (payloads name who is being notified).
ALTER TABLE public.service_outbox ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.service_outbox FROM public, anon, authenticated;

COMMENT ON TABLE public.service_outbox IS
  'C12 durable side-effects. Rows are enqueued IN the transition transaction (commit iff the state change commits) and delivered by drain_service_outbox() with FOR UPDATE SKIP LOCKED + retry/backoff + dead-letter. First consumer: notify-push job-offer delivery, which before this migration was built but never called.';

-- ── ENQUEUE ──────────────────────────────────────────────────────────────────
-- Called from inside a transition's transaction. Plain INSERT on purpose: no HTTP here, because an
-- HTTP call inside the transaction is the very coupling the outbox removes.
CREATE OR REPLACE FUNCTION public.enqueue_service_push(
  p_provider_ids uuid[],
  p_title        text,
  p_body         text,
  p_url          text DEFAULT NULL
) RETURNS uuid
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  INSERT INTO public.service_outbox (consumer, payload)
  VALUES ('notify-push', jsonb_build_object(
    'provider_ids', to_jsonb(p_provider_ids),
    'title', p_title, 'body', p_body, 'url', p_url))
  RETURNING id;
$$;

-- ── RELAY ────────────────────────────────────────────────────────────────────
-- Claims a batch with FOR UPDATE SKIP LOCKED so N relays never fight over the same row, then fires
-- net.http_post (async: it returns a request id, reconciled below). Reuses the platform's existing
-- GUC recipe (app.supabase_functions_url / app.service_role_key) rather than inventing one.
CREATE OR REPLACE FUNCTION public.drain_service_outbox(p_limit int DEFAULT 20)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  r       record;
  n_sent  int := 0;
  v_url   text := current_setting('app.supabase_functions_url', true);
  v_key   text := current_setting('app.service_role_key', true);
  v_req   bigint;
BEGIN
  -- Honest refusal: without the GUCs there is no way to deliver. Say so instead of burning attempts
  -- and dead-lettering perfectly good rows (this is exactly how 9 platform cron jobs silently died).
  IF v_url IS NULL OR v_url = '' OR v_key IS NULL OR v_key = '' THEN
    RETURN jsonb_build_object('ok', false, 'reason',
      'app.supabase_functions_url / app.service_role_key not set on this database', 'sent', 0);
  END IF;

  FOR r IN
    SELECT id, consumer, payload
    FROM public.service_outbox
    WHERE status = 'pending' AND next_attempt_at <= now()
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT p_limit
  LOOP
    SELECT net.http_post(
      url     := v_url || '/' || r.consumer,
      body    := r.payload,
      headers := jsonb_build_object('Authorization', 'Bearer ' || v_key,
                                    'Content-Type',  'application/json'),
      timeout_milliseconds := 10000
    ) INTO v_req;

    UPDATE public.service_outbox
       SET status = 'in_flight', request_id = v_req, attempts = attempts + 1, updated_at = now()
     WHERE id = r.id;
    n_sent := n_sent + 1;
  END LOOP;

  RETURN jsonb_build_object('ok', true, 'sent', n_sent);
END;
$$;

-- ── RECONCILE ────────────────────────────────────────────────────────────────
-- pg_net is asynchronous, so "posted" is not "delivered". Join the response table: 2xx -> done,
-- anything else -> exponential backoff, and dead-letter once max_attempts is spent so a poison row
-- can never loop forever.
CREATE OR REPLACE FUNCTION public.reconcile_service_outbox()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE n_done int := 0; n_retry int := 0; n_dead int := 0;
BEGIN
  WITH resolved AS (
    SELECT o.id, resp.status_code, left(coalesce(resp.content, resp.error_msg, ''), 400) AS msg
    FROM public.service_outbox o
    JOIN net._http_response resp ON resp.id = o.request_id
    WHERE o.status = 'in_flight'
  ),
  finished AS (
    UPDATE public.service_outbox o
       SET status = 'done', last_error = NULL, updated_at = now()
      FROM resolved r
     WHERE o.id = r.id AND r.status_code BETWEEN 200 AND 299
     RETURNING 1
  ),
  failed AS (
    UPDATE public.service_outbox o
       SET status     = CASE WHEN o.attempts >= o.max_attempts THEN 'dead' ELSE 'pending' END,
           -- 2s, 4s, 8s … capped at 30 min
           next_attempt_at = now() + least(power(2, o.attempts) * interval '1 second', interval '30 minutes'),
           last_error = 'HTTP ' || coalesce(r.status_code::text, '?') || ' ' || r.msg,
           request_id = NULL,
           updated_at = now()
      FROM resolved r
     WHERE o.id = r.id AND (r.status_code IS NULL OR r.status_code NOT BETWEEN 200 AND 299)
     RETURNING o.status
  )
  SELECT (SELECT count(*) FROM finished),
         (SELECT count(*) FROM failed WHERE status = 'pending'),
         (SELECT count(*) FROM failed WHERE status = 'dead')
    INTO n_done, n_retry, n_dead;

  RETURN jsonb_build_object('done', n_done, 'retried', n_retry, 'dead', n_dead);
END;
$$;

-- ── THE LESSON FROM THIS SESSION'S IDOR, APPLIED UP FRONT ─────────────────────
-- Postgres grants EXECUTE to PUBLIC on every new function. These three mutate across tenants and are
-- cron/trigger-only, so they are revoked immediately — not after a gate catches them.
REVOKE ALL ON FUNCTION public.enqueue_service_push(uuid[], text, text, text) FROM public, anon, authenticated;
REVOKE ALL ON FUNCTION public.drain_service_outbox(int)                      FROM public, anon, authenticated;
REVOKE ALL ON FUNCTION public.reconcile_service_outbox()                     FROM public, anon, authenticated;

COMMENT ON FUNCTION public.drain_service_outbox(int) IS
  'Cron-only outbox relay. EXECUTE revoked from public/anon/authenticated: it delivers on behalf of every tenant and no caller-owned row exists for RLS to scope.';

COMMIT;
