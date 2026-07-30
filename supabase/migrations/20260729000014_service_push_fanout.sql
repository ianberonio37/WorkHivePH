-- =====================================================================
-- C12 (part 2) · THE FAN-OUT THAT NEVER EXISTED — a hail now actually reaches a provider
-- =====================================================================
-- FOUND 2026-07-29: Web Push (G3) was fully built and NEVER INVOKED. push_subscriptions, the sw.js
-- `push` handler, the VAPID keypair, the in-context subscribe on marketplace-seller.html and the
-- notify-push edge function all shipped - but a repo-wide search found NO caller anywhere. Its own
-- docstring admitted it: "Callers are backend: the broadcast fan-out (DB webhook/cron, future)". So a
-- provider granted permission, subscribed, and received nothing - exactly the failure G3 existed to
-- prevent ("without this, hailing fails on mobile"), while the roadmap counted G3 as delivered on the
-- strength of the subscribe half alone.
--
-- This is the missing half. When a request enters `broadcasting`, the matched provider set is resolved
-- IN THE SAME TRANSACTION and an outbox row is enqueued (mig ...013). Enqueue is a plain INSERT, never
-- an HTTP call: the intent to notify commits if and only if the hail does, and delivery is then the
-- relay's problem - retried, backed off, and dead-lettered instead of silently lost.
--
-- MATCHING is the real predicate, not the feed's coarse one: v_service_open_broadcasts widens to 4x
-- radius because a human scrolling a list benefits from seeing more. A push interrupts someone, so it
-- uses the ACTUAL broadcast_radius_m, online providers only, category-matched, and never the client's
-- own provider profile.

BEGIN;

CREATE OR REPLACE FUNCTION public.fanout_broadcast_push()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
-- PostGIS lives in `extensions` on Supabase, so st_dwithin is unresolvable under a public-only
-- search_path. Same pinned list accept_service_request already uses - matched deliberately rather
-- than schema-qualifying, so every geo function in this arc resolves identically.
SET search_path = pg_catalog, public, extensions
AS $$
DECLARE
  v_ids   uuid[];
  v_label text;
  v_dist  text;
BEGIN
  -- Only on the transition INTO broadcasting (never on every later touch of a broadcasting row).
  IF NEW.status IS DISTINCT FROM 'broadcasting' THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM 'broadcasting' THEN
    RETURN NEW;
  END IF;

  SELECT array_agg(sp.id)
    INTO v_ids
    FROM public.service_providers sp
    LEFT JOIN public.service_catalog c ON c.id = NEW.catalog_item_id
   WHERE sp.availability = 'online'
     AND (NEW.catalog_item_id IS NULL OR c.category = ANY (sp.categories))
     AND (NEW.location IS NULL OR sp.base_location IS NULL
          OR st_dwithin(NEW.location, sp.base_location, NEW.broadcast_radius_m::double precision))
     -- never ping the client's own provider profile with their own hail
     AND (NEW.client_auth_uid IS NULL OR sp.auth_uid IS DISTINCT FROM NEW.client_auth_uid);

  IF v_ids IS NULL OR cardinality(v_ids) = 0 THEN
    RETURN NEW;   -- nobody online in range: not an error, just nothing to deliver
  END IF;

  SELECT COALESCE(c.name, NULLIF(btrim(NEW.custom_scope), ''), 'Service request')
    INTO v_label
    FROM public.service_catalog c WHERE c.id = NEW.catalog_item_id;
  v_label := COALESCE(v_label, NULLIF(btrim(NEW.custom_scope), ''), 'Service request');

  v_dist := COALESCE(split_part(COALESCE(NEW.address, ''), ',', 1), '');

  PERFORM public.enqueue_service_push(
    v_ids,
    CASE WHEN NEW.urgency = 'emergency' THEN 'Emergency job nearby' ELSE 'New job nearby' END,
    v_label || CASE WHEN v_dist <> '' THEN ' - ' || v_dist ELSE '' END,
    '/workhive/marketplace-seller.html?tab=services'
  );

  RETURN NEW;
END;
$$;

-- AFTER, so the row (and its guard triggers) have already settled before we resolve the match set.
DROP TRIGGER IF EXISTS trg_fanout_broadcast_push ON public.service_requests;
CREATE TRIGGER trg_fanout_broadcast_push
  AFTER INSERT OR UPDATE OF status ON public.service_requests
  FOR EACH ROW EXECUTE FUNCTION public.fanout_broadcast_push();

-- Trigger functions are invoked by the trigger machinery, never by a client. Revoked up front rather
-- than after a gate catches it (this session already found one live IDOR from exactly that default).
REVOKE ALL ON FUNCTION public.fanout_broadcast_push() FROM public, anon, authenticated;

COMMENT ON FUNCTION public.fanout_broadcast_push() IS
  'Enqueues a Web Push job-offer to every online, category-matched provider inside broadcast_radius_m when a request enters broadcasting. Closes the G3 gap where notify-push existed but nothing ever called it. Enqueue is transactional (outbox); delivery is retried by drain_service_outbox().';

-- ── the relay schedule ────────────────────────────────────────────────────────
-- Every minute: claim + post, then reconcile the async pg_net responses. Both are idempotent and
-- SKIP LOCKED, so an overlapping run is harmless.
SELECT cron.schedule('service-outbox-drain-1min',     '* * * * *', $c$SELECT public.drain_service_outbox(20);$c$)
WHERE NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'service-outbox-drain-1min');
SELECT cron.schedule('service-outbox-reconcile-1min', '* * * * *', $c$SELECT public.reconcile_service_outbox();$c$)
WHERE NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'service-outbox-reconcile-1min');

COMMIT;
