-- ★THE PROVIDER'S DISPUTED CARD NEVER SAID WHO REPORTED THE PROBLEM, WHEN, OR WHAT IT WAS (2026-11-06, GJ M9 G-SVC hop 1:
-- "the client's problem report puts the job in the provider's disputed bucket").
--
-- raise_service_objection records the client's reason as a job event (to_state 'disputed', actor_role 'client'), and the
-- provider's console showed the job under "Reported by the client" with only the job's own scope text - the reason the
-- client wrote, and when they wrote it, were nowhere on the provider's screen. The provider is the person money can move
-- against in the review; they were told a problem exists without being told what it is, so they could not answer it or
-- call the client about the right thing.
--
-- The report is a fact about the job, so it rides on the job's own read like the review does (20261031000001): two
-- columns appended last (every existing column keeps its position) - reported_at and report_reason, the latest client
-- 'disputed' event that carries a reason (the status-change trigger writes its own client 'disputed' event in the same
-- instant, with no note - measured: picking by time alone returned that one), the reason without the server's own prefix. Security invoker as before (said again, since CREATE OR
-- REPLACE VIEW does not keep it); service_job_events_party_read scopes the subquery to the job's parties.

BEGIN;

create or replace view public.v_service_request_truth with (security_invoker = on) as
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
          WHERE ((o.request_id = r.id) AND (o.status = 'pending'::text))) AS pending_offers,
    1 AS _source_count,
    r.updated_at AS _freshness_ts,
    'service_request_truth:v2'::text AS _canonical_version,
        CASE
            WHEN (r.completed_at IS NULL) THEN NULL::timestamp with time zone
            ELSE (r.completed_at + ((service_knob(r.hive_id, 'completion_window_days'::text))::double precision * '1 day'::interval))
        END AS objection_deadline,
    ( SELECT e.created_at
           FROM service_job_events e
          WHERE ((e.request_id = r.id) AND (e.actor_role = 'admin'::text))
          ORDER BY e.created_at DESC
         LIMIT 1) AS reviewed_at,
    ( SELECT e.note
           FROM service_job_events e
          WHERE ((e.request_id = r.id) AND (e.actor_role = 'admin'::text))
          ORDER BY e.created_at DESC
         LIMIT 1) AS review_note,
    ( SELECT e.created_at
           FROM service_job_events e
          WHERE ((e.request_id = r.id) AND (e.actor_role = 'client'::text) AND (e.to_state = 'disputed'::text) AND (e.note IS NOT NULL))
          ORDER BY e.created_at DESC
         LIMIT 1) AS reported_at,
    ( SELECT regexp_replace(e.note, '^buyer raised a problem inside the objection window: '::text, ''::text)
           FROM service_job_events e
          WHERE ((e.request_id = r.id) AND (e.actor_role = 'client'::text) AND (e.to_state = 'disputed'::text) AND (e.note IS NOT NULL))
          ORDER BY e.created_at DESC
         LIMIT 1) AS report_reason
   FROM ((service_requests r
     LEFT JOIN service_catalog c ON ((c.id = r.catalog_item_id)))
     LEFT JOIN service_providers sp ON ((sp.id = r.matched_provider_id)))
  WHERE ((r.client_auth_uid = auth.uid()) OR ((r.hive_id IS NOT NULL) AND (r.hive_id IN ( SELECT hm.hive_id
           FROM hive_members hm
          WHERE ((hm.auth_uid = auth.uid()) AND (hm.status = 'active'::text))))) OR (r.matched_provider_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids)));

COMMIT;
