-- ─────────────────────────────────────────────────────────────────────────────
-- Anchor the service-hailing Fuel + Engine in canonical_sources (SERVICE_HAILING
-- P1/P2 registration debt — the canonical-anchor gate caught the un-anchored 9
-- tables + 4 views + RPCs on the very next run, exactly as designed; the arc's
-- own rule is "registration in the SAME change", so this closes it immediately).
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
VALUES
  ('service_hailing', 'table', 'service_catalog', 'marketplace', 'on_demand',
   '{"key": ["id"], "segment_values": ["industrial", "consumer"]}'::jsonb,
   'Service-hailing rate card, both segments seeded from day one; consumer rows behind the segment flag until P8.'),
  ('service_hailing', 'table', 'service_providers', 'marketplace', 'realtime',
   '{"key": ["id"], "availability_values": ["online", "offline", "on_job"], "privacy": "live_location has NO broad column grant; v_service_job_tracking is the only read path"}'::jsonb,
   'Provider registry (freelancers + hive companies). verified + on_job are system-set (guard trigger).'),
  ('service_hailing', 'table', 'service_requests', 'marketplace', 'realtime',
   '{"key": ["id"], "status_machine": ["requested", "broadcasting", "accepted", "en_route", "on_site", "in_progress", "completed", "settled", "cancelled_by_client", "cancelled_by_provider", "expired", "disputed"]}'::jsonb,
   'The hail. Transitions DB-enforced by guard_service_request_status; journal via trg_journal_service_request.'),
  ('service_hailing', 'table', 'service_offers', 'marketplace', 'realtime',
   '{"key": ["request_id", "provider_id"], "kind_values": ["accept", "quote"]}'::jsonb,
   'Provider responses: instant accepts + quotes. One per provider per request.'),
  ('service_hailing', 'table', 'service_job_events', 'marketplace', 'realtime',
   '{"append_only": true}'::jsonb,
   'Append-only job timeline written by the transition journaler — the record outlives the action.'),
  ('service_hailing', 'table', 'service_credit_ledger', 'marketplace', 'on_demand',
   '{"append_only": true, "balance": "SUM(amount) per account", "writes": "backend/GUC only — the trust-forge pattern extended to money"}'::jsonb,
   'Founder-income credit ledger. No client write path; non-withdrawable prepaid platform fees.'),
  ('service_hailing', 'table', 'service_credit_topups', 'marketplace', 'on_demand',
   '{"key": ["gcash_ref"], "status_values": ["pending_verification", "verified", "rejected"], "verify": "founder/admin only; verification mints the ledger entry"}'::jsonb,
   'GCash P2P top-up intake + founder verification queue.'),
  ('service_hailing', 'table', 'service_vouchers', 'marketplace', 'on_demand',
   '{"key": ["code"], "kind_values": ["percent", "fixed"]}'::jsonb,
   'Founder-minted acquisition vouchers (platform-funded).'),
  ('service_hailing', 'table', 'service_voucher_redemptions', 'marketplace', 'on_demand',
   '{"key": ["voucher_id", "request_id"], "gate": "verified completion only"}'::jsonb,
   'Voucher redemption records, completion-gated.'),
  ('service_hailing', 'view', 'v_service_provider_truth', 'marketplace', 'realtime',
   '{"boundary": "public directory columns only; live_location deliberately absent"}'::jsonb,
   'Provider directory truth + verified completed-jobs count.'),
  ('service_hailing', 'view', 'v_service_request_truth', 'marketplace', 'realtime',
   '{"boundary": "re-asserted in view: client, their hive, matched provider"}'::jsonb,
   'Request truth for the request''s parties, with catalog + provider + offer rollup.'),
  ('service_hailing', 'view', 'v_service_open_broadcasts', 'marketplace', 'realtime',
   '{"boundary": "caller''s provider identities; never own hails; coarse area only pre-accept"}'::jsonb,
   'A provider''s open-broadcast feed (category + radius scoped, distance_km).'),
  ('service_hailing', 'view', 'v_service_job_tracking', 'marketplace', 'realtime',
   '{"boundary": "active-job parties only (en_route/on_site/in_progress)", "privacy": "the ONLY live_location read path (D8)"}'::jsonb,
   'Live provider location for an active job — client + provider only.'),
  ('service_hailing', 'rpc', 'accept_service_request', 'marketplace', 'on_demand',
   '{"signature": "accept_service_request(p_request_id uuid, p_eta_minutes integer) RETURNS jsonb", "side_effects": ["service_requests.status broadcasting->accepted (atomic, one winner)", "service_offers upsert selected", "service_providers.availability -> on_job"]}'::jsonb,
   'Atomic first-accept-wins. 0-row race loss surfaced as lost_race_or_closed — fixes the reference TOCTOU.'),
  ('service_hailing', 'rpc', 'submit_service_quote', 'marketplace', 'on_demand',
   '{"signature": "submit_service_quote(p_request_id uuid, p_price numeric, p_eta_minutes integer, p_message text) RETURNS jsonb", "side_effects": ["service_offers upsert kind=quote"]}'::jsonb,
   'Quote-mode response to a broadcasting request.'),
  ('service_hailing', 'rpc', 'select_quote', 'marketplace', 'on_demand',
   '{"signature": "select_quote(p_offer_id uuid) RETURNS jsonb", "side_effects": ["service_requests.status broadcasting->accepted", "offers selected/declined", "provider on_job"]}'::jsonb,
   'The client picks a quote — atomic match.'),
  ('service_hailing', 'rpc', 'my_service_provider_ids', 'marketplace', 'on_demand',
   '{"signature": "my_service_provider_ids() RETURNS setof uuid", "side_effects": []}'::jsonb,
   'DEFINER identity helper (user_hive_ids pattern): the caller''s provider ids, incl. hive providers via membership.')
ON CONFLICT DO NOTHING;
