-- 20260826000001_push_dedupe_window.sql  (T110, 2026-08-26)
--
-- THE STORM PROBLEM, narrow slice. Every notification event enqueues its own outbox row and the
-- drain sends one push per row -- there is no coalescing anywhere in the lane. In a busy hive
-- (T61's 20-member fixture; T110's "50 events an hour") a worker can be pushed the same sentence
-- several times in a minute: the same PM going overdue as two triggers fire, a supervisor's
-- repeated save, a retrying client. Nobody wants the same unsent push twice.
--
-- WHAT THIS DOES, and deliberately no more: refuse to enqueue a push that is BYTE-IDENTICAL
-- (same recipients, title, body, url) to one already sitting UNSENT in the outbox inside a short
-- window. It returns the existing row's id, so every caller keeps working unchanged -- the
-- contract is still "an id comes back".
--
-- WHAT IT DOES NOT DO, on purpose: it does not merge DIFFERENT notifications into a digest
-- ("3 new replies"), which is a design decision about wording and cadence, not a dedupe -- that
-- stays T110's larger item. And it never suppresses a push whose predecessor has already been
-- SENT: if you were told an hour ago and it happens again, that is news, not a duplicate.
--
-- The window is short (2 minutes) so a genuine repeat later still reaches the person.

CREATE OR REPLACE FUNCTION public.enqueue_user_push(p_auth_uids uuid[], p_title text, p_body text, p_url text DEFAULT NULL::text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_payload jsonb := jsonb_build_object(
    'auth_uids', to_jsonb(p_auth_uids),
    'title', p_title, 'body', p_body, 'url', p_url);
  v_existing uuid;
  v_id uuid;
BEGIN
  -- an identical push still WAITING to be sent: hand back the pending row rather than adding a
  -- second one. status is only ever 'dead'/'done' once the drain has finished with a row, so
  -- "not yet terminal" is the pending set.
  SELECT id INTO v_existing
  FROM public.service_outbox
  WHERE consumer = 'notify-push'
    AND payload = v_payload
    AND status NOT IN ('done', 'dead')
    AND created_at > now() - interval '2 minutes'
  ORDER BY created_at DESC
  LIMIT 1;

  IF v_existing IS NOT NULL THEN
    RETURN v_existing;
  END IF;

  INSERT INTO public.service_outbox (consumer, payload)
  VALUES ('notify-push', v_payload)
  RETURNING id INTO v_id;
  RETURN v_id;
END;
$function$;

COMMENT ON FUNCTION public.enqueue_user_push(uuid[], text, text, text) IS
  'Enqueue a web push. Dedupes byte-identical UNSENT pushes inside a 2-minute window (T110): '
  'the same sentence is never queued twice to the same people, while a genuine repeat after the '
  'first one has been delivered still gets through. Digest-style coalescing of DIFFERENT '
  'notifications is deliberately not done here.';
