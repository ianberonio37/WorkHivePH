-- 20260729000017_fanout_urgency_vocabulary.sql
--
-- THE DEFECT: fanout_broadcast_push titled the push
--     CASE WHEN NEW.urgency = 'emergency' THEN 'Emergency job nearby' ELSE 'New job nearby' END
-- and 'emergency' is a value the column FORBIDS. service_requests_urgency_check allows exactly
-- {low, normal, high, critical}, and the hail form offers exactly those four. So the urgent branch
-- could never be reached: a CRITICAL hail - "production is down" - pushed to every nearby provider
-- with the same words as a "whenever convenient" one.
--
-- Nothing failed. No error was raised, no gate reddened, and the push went out looking healthy. This
-- is the same shape as the is_anomaly='ANOMALY' predicate that killed four surfaces
-- ([[feedback_view_predicate_forbidden_by_check]]): a branch written against a vocabulary that does
-- not exist reads as working code and is simply never taken.
--
-- A push interrupts someone. If it cannot tell them the difference between a downed line and a leaky
-- tap, the interruption has spent its credibility for nothing.
CREATE OR REPLACE FUNCTION public.fanout_broadcast_push()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public', 'extensions'
AS $function$
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
    -- The REAL vocabulary. 'critical' is the form's "production is down"; 'high' is "today if
    -- possible". Both earn the interruption; low/normal do not.
    CASE WHEN NEW.urgency IN ('critical', 'high') THEN 'Urgent job nearby'
         ELSE 'New job nearby' END,
    v_label || CASE WHEN v_dist <> '' THEN ' - ' || v_dist ELSE '' END,
    '/workhive/marketplace-seller.html?tab=services'
  );

  RETURN NEW;
END;
$function$;
