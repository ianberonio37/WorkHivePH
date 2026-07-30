-- =====================================================================
-- Arc II registration cascade — anchor the three objects C12/C15 introduced
-- =====================================================================
-- The canonical-anchor gate caught what the migrations alone did not: a new table or truth-view is
-- not "shipped" until it is REGISTERED as a canonical source with an owner and a contract. Without
-- the row, nothing records who owns the object, what it is for, or how fresh its data should be, and
-- the next session reads it as an orphan. Registration is part of the build, not paperwork.
--
-- TWO traps caught here, both by reading the result instead of the gate:
--   1. `contract` is JSONB, not prose. A first attempt passed a sentence and the whole transaction
--      rolled back on "Token ... is invalid" — while the gate still went GREEN, because it parses this
--      migration's TEXT rather than querying the live registry. The anchor looked registered and was not.
--   2. The PRIMARY KEY is `(domain)` ALONE — this registry is keyed one row per DOMAIN, and existing
--      entries use the object's own name as the domain (`service_offers`, `service_requests_raw`, …).
--      Registering all three under a shared 'service_hailing' domain collided with the row that key
--      already holds, and `ON CONFLICT DO NOTHING` swallowed it into a silent `INSERT 0 0` — a zero-row
--      write is not an error, so nothing complained. Each object gets its own domain key.
-- Verified by reading the rows back AFTER commit, never by trusting the gate that motivated the change.

BEGIN;

INSERT INTO public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
VALUES
  ('service_outbox', 'table', 'service_outbox', 'marketplace', 'realtime',
   jsonb_build_object(
     'key', jsonb_build_array('id'),
     'status_machine', jsonb_build_array('pending', 'in_flight', 'done', 'dead'),
     'boundary', 'infrastructure - RLS on with NO client grant; payloads name who is being notified',
     'enqueue', 'in the SAME transaction as the transition (commits iff the state change commits)',
     'delivery', 'drain_service_outbox() claims FOR UPDATE SKIP LOCKED and posts via pg_net; reconcile_service_outbox() resolves against net._http_response with exponential backoff, then dead-letters'),
   'C12 durable side-effects (roadmap 4b). The delivery spine for boundary-crossing effects; its first consumer is the Web Push job-offer fan-out, which before this shipped was fully built and never called.'),

  ('service_slo_targets', 'table', 'service_slo_targets', 'analytics-engineer', 'manual',
   jsonb_build_object(
     'key', jsonb_build_array('sli'),
     'slis', jsonb_build_array('allocation_rate', 'time_to_accept_p50', 'completion_rate'),
     'boundary', 'readable by authenticated - a platform reliability target is not tenant data',
     'tuning', 'DATA, not code: changing a target is a business decision (Ian), never a migration'),
   'C15 reliability targets (roadmap 4b). Read by v_service_slo; seeded with opening defaults that are explicitly vetoable.'),

  ('v_service_slo', 'view', 'v_service_slo', 'analytics-engineer', 'live',
   jsonb_build_object(
     'boundary', 'aggregate marketplace health - no row is attributable to a hive through it, so authenticated may read it',
     'null_semantics', 'value IS NULL means NOT MEASURABLE YET (empty denominator) - deliberately distinct from 0, which would be a fabricated breach',
     'sources', jsonb_build_array('service_requests', 'service_slo_targets')),
   'C15 SLI board (roadmap 4b). Each SLI is measured against its own target window; a breach is a business signal, reported loudly and never failing a gate.')
ON CONFLICT DO NOTHING;

COMMIT;
