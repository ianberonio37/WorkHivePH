-- 20260729000018_notify_service_cancellation.sql
--
-- THE DEFECT, surfaced by the role-pair rule (2026-07-29). `SJ-J09-cancel-client` and
-- `SJ-J10-cancel-provider` were both walk-complete having been walked ONLY from the canceller's side.
-- Declaring their role pair (`canceller x notified`) made the missing half measurable, and the missing
-- half turned out to be missing from the PRODUCT, not just from the walk:
--
--   a search of every function touching 'cancelled_by_client' / 'cancelled_by_provider' returns
--   exactly two - sync_provider_availability (which frees the provider back to 'online') and the
--   status guard (which permits the transition). NOTHING TELLS THE OTHER PARTY.
--
-- So a client cancels a job while the provider is EN ROUTE, and the provider is never told. Their
-- availability quietly flips back to online and the job disappears from their list. They keep driving
-- to a site for work that no longer exists - a real trip, real fuel, on a platform whose whole promise
-- to a provider is that a hail is worth answering.
--
-- The push rail already exists and is already used for "New job nearby": push_subscriptions, the
-- transactional outbox, the drain/reconcile pair, and notify-push - which accepts BOTH `provider_ids`
-- and `auth_uids`, so both directions are deliverable without new infrastructure.
--
-- A NEW FUNCTION NAME, NOT AN OVERLOAD. `enqueue_service_push(uuid[], text, text, text)` already
-- exists; adding a second signature would create a PostgREST overload and PGRST203 would kill the
-- endpoint for every caller ([[feedback_rpc_overload_pgrst203_kills_endpoint]]).
CREATE OR REPLACE FUNCTION public.enqueue_service_push_uids(
  p_auth_uids uuid[], p_title text, p_body text, p_url text DEFAULT NULL)
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

REVOKE EXECUTE ON FUNCTION public.enqueue_service_push_uids(uuid[], text, text, text) FROM anon, authenticated;

CREATE OR REPLACE FUNCTION public.notify_service_cancellation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_label text;
  v_who   text;
BEGIN
  -- Only on the transition INTO a cancelled state, never on a later touch of an already-cancelled row
  -- (the same re-fire discipline the broadcast fan-out needed: a duplicate push about a cancellation
  -- is worse than none, because the second one implies a second job).
  IF NEW.status NOT IN ('cancelled_by_client', 'cancelled_by_provider') THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.status = NEW.status THEN
    RETURN NEW;
  END IF;

  SELECT COALESCE(c.name, NULLIF(btrim(NEW.custom_scope), ''), 'the job')
    INTO v_label
    FROM (SELECT 1) _x
    LEFT JOIN public.service_catalog c ON c.id = NEW.catalog_item_id;
  v_label := COALESCE(v_label, 'the job');

  IF NEW.status = 'cancelled_by_client' THEN
    -- Nobody to tell if nobody was matched: a hail cancelled while still broadcasting was never
    -- anyone's job, and paging every provider who saw it would be noise about work they never had.
    IF NEW.matched_provider_id IS NULL THEN
      RETURN NEW;
    END IF;
    PERFORM public.enqueue_service_push_uids(
      ARRAY(SELECT sp.auth_uid FROM public.service_providers sp
             WHERE sp.id = NEW.matched_provider_id AND sp.auth_uid IS NOT NULL),
      'Job cancelled',
      COALESCE(NEW.client_worker_name, 'The client') || ' cancelled ' || v_label ||
        CASE WHEN NEW.address IS NOT NULL AND btrim(NEW.address) <> ''
             THEN ' at ' || split_part(NEW.address, ',', 1) ELSE '' END ||
        '. Stand down - do not travel.',
      '/workhive/marketplace-seller.html?tab=services');
  ELSE
    IF NEW.client_auth_uid IS NULL THEN
      RETURN NEW;
    END IF;
    SELECT COALESCE(sp.display_name, 'The provider') INTO v_who
      FROM public.service_providers sp WHERE sp.id = NEW.matched_provider_id;
    PERFORM public.enqueue_service_push_uids(
      ARRAY[NEW.client_auth_uid],
      'Provider cancelled',
      COALESCE(v_who, 'The provider') || ' cancelled ' || v_label ||
        '. Hail again to find someone else.',
      '/workhive/marketplace.html');
  END IF;

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_notify_service_cancellation ON public.service_requests;
CREATE TRIGGER trg_notify_service_cancellation
AFTER UPDATE OF status ON public.service_requests
FOR EACH ROW EXECUTE FUNCTION public.notify_service_cancellation();
