-- ============================================================================
-- TELL THE BUYER THE CLOCK STARTED
--
-- The window only protects a buyer who KNOWS it is running. That is not a
-- nicety, it is the entire measured difference between the designs (plan §3b):
--
--   WINDOW, no reminder      P95.1M   -72%   91% of STRICT's benefit
--   WINDOW + in-app badge    P75.6M   -78%   98%
--   WINDOW + push            P55.3M   -84%   105%   <- beats STRICT outright
--
-- A window with no notification is a slower way to lose the same money: the
-- provider marks done, three days pass in silence, and it auto-settles against
-- a buyer who never had the chance to object. So the push IS the mechanism,
-- not decoration on top of it.
--
-- Reaches the BUYER, not providers. `enqueue_service_push` only speaks
-- provider_ids, but the notify-push consumer already accepts an `auth_uids`
-- key and resolves it straight against push_subscriptions.auth_uid -- checked
-- in supabase/functions/notify-push/index.ts before writing this, because
-- enqueuing a payload shape the consumer ignores is how a notification ships
-- "working" and silently delivers nothing.
--
-- The deadline in the message is computed from NEW.completed_at, not by
-- calling service_objection_deadline() -- an AFTER trigger could otherwise
-- race its own row. Same arithmetic, same knob, so the push and the sweep can
-- never quote different dates.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.enqueue_user_push(p_auth_uids uuid[], p_title text,
                                                    p_body text, p_url text DEFAULT NULL)
 RETURNS uuid
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
  INSERT INTO public.service_outbox (consumer, payload)
  VALUES ('notify-push', jsonb_build_object(
    'auth_uids', to_jsonb(p_auth_uids),
    'title', p_title, 'body', p_body, 'url', p_url))
  RETURNING id;
$function$;

-- Infrastructure, not a user capability: anyone able to call this could push
-- arbitrary copy to any user. Same posture as enqueue_service_push.
REVOKE ALL ON FUNCTION public.enqueue_user_push(uuid[], text, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.enqueue_user_push(uuid[], text, text, text) FROM anon;
REVOKE ALL ON FUNCTION public.enqueue_user_push(uuid[], text, text, text) FROM authenticated;

CREATE OR REPLACE FUNCTION public.fanout_completion_push()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public', 'extensions'
AS $function$
DECLARE
  v_label    text;
  v_deadline timestamptz;
BEGIN
  -- Only on the transition INTO completed, never on a later touch of a
  -- completed row -- otherwise every edit re-pushes and the buyer learns to
  -- ignore it, which costs exactly the protection this exists to buy.
  IF NEW.status IS DISTINCT FROM 'completed' THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM 'completed' THEN
    RETURN NEW;
  END IF;
  IF NEW.client_auth_uid IS NULL THEN
    RETURN NEW;   -- nobody to tell; not an error
  END IF;

  SELECT COALESCE(c.name, NULLIF(btrim(NEW.custom_scope), ''), 'Your job')
    INTO v_label
    FROM public.service_catalog c WHERE c.id = NEW.catalog_item_id;
  v_label := COALESCE(v_label, NULLIF(btrim(NEW.custom_scope), ''), 'Your job');

  v_deadline := COALESCE(NEW.completed_at, now())
              + (public.service_knob(NEW.hive_id, 'completion_window_days') * interval '1 day');

  PERFORM public.enqueue_user_push(
    ARRAY[NEW.client_auth_uid],
    'Job marked done',
    -- Names the DEADLINE and the CONSEQUENCE. "Please confirm" would leave the
    -- buyer unaware that silence is itself an answer here.
    v_label || ' was marked done. Confirm payment, or raise a problem by '
      || to_char(v_deadline AT TIME ZONE 'Asia/Manila', 'Mon FMDD')
      || '. After that it settles automatically.',
    '/workhive/marketplace.html?section=services'
  );

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_fanout_completion_push ON public.service_requests;
CREATE TRIGGER trg_fanout_completion_push
  AFTER INSERT OR UPDATE OF status ON public.service_requests
  FOR EACH ROW EXECUTE FUNCTION public.fanout_completion_push();
