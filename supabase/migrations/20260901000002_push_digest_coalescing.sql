-- T110 (notification storms) — digest coalescing on the EXISTING 2-minute dedupe window (Ian default,
-- 2026-09-01). The prior migration (20260826000001) dedupes BYTE-IDENTICAL pushes; its own comment left
-- coalescing DIFFERENT notifications open. This closes it, keyed on an ADDITIVE p_category param (default
-- null) so every existing caller is byte-for-byte unchanged — coalescing only engages for a caller that
-- opts in by naming its notification category.
--
-- Behaviour:
--   • p_category NULL  → exactly the old function (byte-identical dedupe only). No caller breaks.
--   • p_category set   → if a NON-terminal push to the SAME recipients + SAME category exists in the
--     window, UPDATE it in place to a digest ("N new <category>", N incremented and HONEST — it counts
--     every push it absorbed, never a frozen "3" while a 4th lands) and return that row's id. Otherwise
--     insert normally, seeded with digest_count=1. A genuine repeat AFTER the window still gets through.
-- The count lives in the payload (digest_count) so the drain and any later coalesce read it back.
--
-- ★DROP the old 4-arg signature FIRST, then create the 5-arg-with-default. A bare CREATE OR REPLACE
-- with a new arg count makes an OVERLOAD, not a replacement — and two overloads make a 4-arg call
-- ambiguous to PostgREST (PGRST203 kills the endpoint, a lesson already paid for here). With the old
-- signature dropped, a 4-arg call resolves to this one function via p_category's default. No dependents:
-- enqueue_user_push is called by application/edge code, not by a trigger or policy.
DROP FUNCTION IF EXISTS public.enqueue_user_push(uuid[], text, text, text);

CREATE OR REPLACE FUNCTION public.enqueue_user_push(
    p_auth_uids uuid[], p_title text, p_body text,
    p_url text DEFAULT NULL::text, p_category text DEFAULT NULL::text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_payload jsonb := jsonb_build_object(
    'auth_uids', to_jsonb(p_auth_uids),
    'title', p_title, 'body', p_body, 'url', p_url,
    'category', p_category, 'digest_count', 1);
  v_existing uuid;
  v_prev_count int;
  v_id uuid;
BEGIN
  -- byte-identical dedupe (the original contract) — unchanged, always first.
  SELECT id INTO v_existing
  FROM public.service_outbox
  WHERE consumer = 'notify-push' AND payload = v_payload
    AND status NOT IN ('done', 'dead') AND created_at > now() - interval '2 minutes'
  ORDER BY created_at DESC LIMIT 1;
  IF v_existing IS NOT NULL THEN
    RETURN v_existing;
  END IF;

  -- digest coalescing — only when the caller named a category.
  IF p_category IS NOT NULL THEN
    SELECT id, COALESCE((payload->>'digest_count')::int, 1)
      INTO v_existing, v_prev_count
    FROM public.service_outbox
    WHERE consumer = 'notify-push'
      AND status NOT IN ('done', 'dead')
      AND created_at > now() - interval '2 minutes'
      AND payload->>'category' = p_category
      AND (payload->'auth_uids') = to_jsonb(p_auth_uids)
    ORDER BY created_at DESC LIMIT 1;

    IF v_existing IS NOT NULL THEN
      UPDATE public.service_outbox
      SET payload = payload
            || jsonb_build_object(
                 'digest_count', v_prev_count + 1,
                 'title', (v_prev_count + 1) || ' new ' || p_category,
                 'body',  (v_prev_count + 1) || ' new ' || p_category || ' — open to catch up.')
      WHERE id = v_existing;
      RETURN v_existing;
    END IF;
  END IF;

  INSERT INTO public.service_outbox (consumer, payload)
  VALUES ('notify-push', v_payload)
  RETURNING id INTO v_id;
  RETURN v_id;
END;
$function$;

COMMENT ON FUNCTION public.enqueue_user_push(uuid[], text, text, text, text) IS
  'Enqueue a web push. (1) Dedupes byte-identical UNSENT pushes in a 2-minute window (T110). '
  '(2) With p_category set, coalesces DIFFERENT same-category pushes to the same recipients in that '
  'same window into an honest "N new <category>" digest (digest_count increments per absorbed push). '
  'p_category NULL keeps the original behaviour exactly, so existing callers are unaffected.';
