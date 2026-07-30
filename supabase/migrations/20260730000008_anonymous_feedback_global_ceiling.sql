-- 20260730000008_anonymous_feedback_global_ceiling.sql
--
-- The public feedback form's rate limit was EVADABLE, and the evasion needed no tooling: vary `worker_name`.
--
-- `check_platform_feedback_rate_limit` allows 5 submissions per hour per identity, where identity is
-- COALESCE(auth_uid::text, worker_name, contact_email, 'anonymous'). `platform_feedback` is anon-writable
-- (policy `feedback anon submit`), so for an unauthenticated submitter that key is a field the CLIENT supplies
-- and every new name is a fresh bucket. Probed live before this migration: six submissions under six names,
-- all six accepted; the same six under ONE name, the sixth correctly refused with 23P01. The limit was doing
-- precisely what it said and protecting nothing.
--
-- FIX (Ian's choice between two real trades): keep the per-identity bucket and add a PLATFORM-WIDE ceiling of
-- 20 anonymous submissions per hour, keyed on `auth_uid IS NULL` rather than on the coalesced identity —
-- because a bound the client can move by changing a string is not a bound. An honest anonymous user is
-- unaffected; a spammer minting names now hits a wall they cannot rename their way past. The alternative
-- (bucket all anonymous together at 5/hour) was rejected because it would turn away legitimate feedback in a
-- busy hour.
--
-- Signed-in submitters are untouched: their bucket is already an id they cannot forge.
--
-- Same ERRCODE 23P01 as the existing limit, so the client's friendly toast keeps working with no frontend
-- change. Extracted with pg_get_functiondef and given one anchored insertion, the builder asserting each
-- anchor appears exactly once.

CREATE OR REPLACE FUNCTION public.check_platform_feedback_rate_limit()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_recent_count integer;
  v_identity     text;
  v_anon_count   integer;
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

  -- ── THE GLOBAL ANONYMOUS CEILING (mig 20260730000008) ─────────────────────────────────────────────
  -- The per-identity limit above buckets on
  --     COALESCE(NEW.auth_uid::text, NEW.worker_name, NEW.contact_email, 'anonymous')
  -- and `platform_feedback` is anon-writable, so for an unauthenticated submitter the bucket key is a field
  -- THE CLIENT SUPPLIES. Probed live 2026-07-30: six submissions under six different worker_names were ALL
  -- accepted, because each name is its own bucket. The limit worked exactly as written and protected nothing
  -- against anyone willing to type a different name ([[feedback_free_text_identity_is_a_claim]]).
  --
  -- Two fixes were possible and they trade differently, so Ian chose rather than me:
  --   * bucket every anonymous submitter as 'anonymous'  -> spam-proof, but ALL anonymous users then share one
  --     5/hour bucket and a busy hour turns away legitimate feedback;
  --   * keep the per-name bucket AND add a platform-wide anonymous ceiling  -> chosen. An honest anonymous
  --     user is unaffected (they would need >5 of their own to notice anything), while a spammer minting fresh
  --     names hits the global wall.
  --
  -- 20/hour is 4 distinct anonymous submitters at their full individual allowance. It is deliberately keyed on
  -- `auth_uid IS NULL` and NOT on the coalesced identity: the whole point is a bound the client cannot move by
  -- changing a string. Signed-in users are untouched by it — their bucket is already an id they cannot forge.
  IF NEW.auth_uid IS NULL THEN
    SELECT COUNT(*) INTO v_anon_count
      FROM public.platform_feedback
     WHERE created_at > now() - interval '1 hour'
       AND auth_uid IS NULL;
    IF v_anon_count >= 20 THEN
      RAISE EXCEPTION 'Feedback rate limit reached: the anonymous hourly ceiling (20) is full. Sign in to submit, or try again shortly.'
        USING ERRCODE = '23P01';   -- same code as the per-identity limit, so the client's existing toast works
    END IF;
  END IF;

  RETURN NEW;
END;
$function$;
