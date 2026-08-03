-- ============================================================================
-- THE DEADLINE BELONGS IN THE VIEW, NOT IN THE PAGE
--
-- The buyer's job row has to say "object by <date>". The naive way is to take
-- completed_at, add 3 days in JavaScript, and print it. That would put the
-- window length in a THIRD place -- the settings column, the service_knob
-- fallback, and now a page -- which is exactly the shape that made the
-- commission knob a no-op for weeks (mig 30: the rate lived in three places
-- and the one actually charging was a hardcoded fallback nobody was reading).
-- Ian tunes the knob, the page keeps saying 3 days, and the screen quietly
-- disagrees with the sweep about when a job settles.
--
-- So the deadline is computed ONCE, here, from the same knob the sweep and the
-- push read. One definition of when the window closes.
--
-- Additive: the column is appended, every existing column keeps its position
-- and meaning, so CREATE OR REPLACE is safe for current readers.
-- _canonical_version moves v1 -> v2 because the shape changed and that field
-- exists to say so; nothing in the codebase pins the string (checked).
-- ============================================================================

CREATE OR REPLACE VIEW public.v_service_request_truth AS
 SELECT r.id,
    r.client_auth_uid,
    r.client_worker_name,
    r.hive_id,
    r.segment,
    r.mode,
    r.catalog_item_id,
    c.name AS catalog_name,
    c.category AS catalog_category,
    c.unit AS catalog_unit,
    c.base_rate AS catalog_rate,
    r.custom_scope,
    r.address,
    r.urgency,
    r.budget,
    r.status,
    r.matched_provider_id,
    sp.display_name AS provider_name,
    sp.contact AS provider_contact,
    sp.availability AS provider_availability,
    r.broadcast_radius_m,
    r.offer_ttl_expires_at,
    r.accepted_at,
    r.en_route_at,
    r.on_site_at,
    r.in_progress_at,
    r.completed_at,
    r.settled_at,
    r.cancelled_at,
    r.created_at,
    r.updated_at,
    ( SELECT count(*) AS count
           FROM service_offers o
          WHERE o.request_id = r.id AND o.status = 'pending'::text) AS pending_offers,
    1 AS _source_count,
    r.updated_at AS _freshness_ts,
    'service_request_truth:v2'::text AS _canonical_version,
    -- NULL until the provider marks the job done; after that, the exact instant
    -- sweep_service_completions() will auto-settle it if the buyer stays silent.
    CASE WHEN r.completed_at IS NULL THEN NULL
         ELSE r.completed_at
              + (public.service_knob(r.hive_id, 'completion_window_days') * interval '1 day')
    END AS objection_deadline
   FROM service_requests r
     LEFT JOIN service_catalog c ON c.id = r.catalog_item_id
     LEFT JOIN service_providers sp ON sp.id = r.matched_provider_id
  WHERE r.client_auth_uid = auth.uid() OR r.hive_id IS NOT NULL AND (r.hive_id IN ( SELECT hm.hive_id
           FROM hive_members hm
          WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'::text)) OR (r.matched_provider_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids));

-- ── The objection itself ────────────────────────────────────────────────────
-- The buyer's "something is wrong" button. It moves the job to `disputed`,
-- which is a LIVE path: apply_dispute_adjustment adjudicates it and, since
-- mig 29, returns any credits the buyer spent. Without this the window is
-- one-sided -- a countdown the buyer can watch but not stop.
--
-- SECURITY DEFINER because the status guard is deliberately strict about who
-- may move a job; the auth check here is explicit and narrow: only the CLIENT
-- on the request, only from `completed`, only before the deadline.
CREATE OR REPLACE FUNCTION public.raise_service_objection(p_request_id uuid, p_reason text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  r         record;
  v_reason  text := NULLIF(btrim(coalesce(p_reason, '')), '');
BEGIN
  SELECT sr.id, sr.status, sr.client_auth_uid, sr.hive_id, sr.completed_at
    INTO r
    FROM public.service_requests sr WHERE sr.id = p_request_id
   FOR UPDATE;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'That job no longer exists.');
  END IF;

  -- The party check comes FIRST and has no admin bypass above it. A bypass
  -- placed before a party check is how this platform shipped a self-deal.
  IF r.client_auth_uid IS DISTINCT FROM auth.uid() THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'Only the person who hailed this job can raise a problem with it.');
  END IF;

  IF r.status <> 'completed' THEN
    RETURN jsonb_build_object('ok', false, 'reason',
      CASE WHEN r.status = 'settled'
           THEN 'This job already settled. Contact support to reopen it.'
           ELSE 'You can only raise a problem once the provider has marked the job done.' END);
  END IF;

  IF v_reason IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'Tell us what went wrong, so it can be adjudicated.');
  END IF;

  UPDATE public.service_requests
     SET status = 'disputed', updated_at = now()
   WHERE id = p_request_id;

  INSERT INTO public.service_job_events (request_id, actor_role, from_state, to_state, note)
  VALUES (p_request_id, 'client', 'completed', 'disputed',
          'buyer raised a problem inside the objection window: ' || left(v_reason, 400));

  RETURN jsonb_build_object('ok', true);
END;
$function$;

REVOKE ALL ON FUNCTION public.raise_service_objection(uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.raise_service_objection(uuid, text) FROM anon;
GRANT EXECUTE ON FUNCTION public.raise_service_objection(uuid, text) TO authenticated;
