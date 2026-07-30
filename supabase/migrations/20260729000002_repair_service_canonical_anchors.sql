-- =====================================================================
-- REPAIR · the service-hailing canonical anchors that were SILENTLY DROPPED
-- =====================================================================
-- Found 2026-07-29 while registering the two money views: `INSERT 0 0`.
--
-- public.canonical_sources has its PRIMARY KEY on `domain` ALONE - `domain` is a per-OBJECT
-- slug in this table (see achievement_xp_log / achievement_xp_log_raw), NOT a subject area.
-- Migration 20260728000041 registered all 17 service-hailing objects with the SAME literal
-- domain 'service_hailing' under ON CONFLICT DO NOTHING, so row 1 (service_catalog) inserted
-- and rows 2-17 silently conflicted away. No error was raised and nothing surfaced: the
-- canonical-anchor GATE reads the mined canonical_registry.json (file-derived), so it stayed
-- green while the DB registry held 1 of 17. Textbook "a 0-row write is not an error" - the
-- write reported success and 16 anchors were never there.
--
-- Repair: one row per object with a UNIQUE domain slug, following the table's own convention
-- (`<name>_raw` for a base table that also has a truth view; the bare name otherwise).
-- Idempotent: ON CONFLICT (domain) DO UPDATE, so re-running reconciles rather than skipping.

BEGIN;

INSERT INTO public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
VALUES
  -- ── Fuel (tables) ────────────────────────────────────────────────────────
  ('service_catalog', 'table', 'service_catalog', 'marketplace', 'on_demand',
   '{"key": ["id"], "segment_values": ["industrial", "consumer"]}'::jsonb,
   'Service-hailing rate card, both segments seeded from day one; consumer rows behind the segment flag until P8.'),
  ('service_providers_raw', 'table', 'service_providers', 'marketplace', 'realtime',
   '{"key": ["id"], "availability_values": ["online", "offline", "on_job"], "privacy": "live_location has NO broad column grant; v_service_job_tracking is the only read path"}'::jsonb,
   'Provider registry (freelancers + hive companies). verified + on_job are system-set (guard trigger).'),
  ('service_requests_raw', 'table', 'service_requests', 'marketplace', 'realtime',
   '{"key": ["id"], "status_machine": ["requested", "broadcasting", "accepted", "en_route", "on_site", "in_progress", "completed", "settled", "cancelled_by_client", "cancelled_by_provider", "expired", "disputed"]}'::jsonb,
   'The hail. Transitions DB-enforced by guard_service_request_status; journal via trg_journal_service_request.'),
  ('service_offers', 'table', 'service_offers', 'marketplace', 'realtime',
   '{"key": ["request_id", "provider_id"], "kind_values": ["accept", "quote"]}'::jsonb,
   'Provider responses: instant accepts + quotes. One per provider per request.'),
  ('service_job_events', 'table', 'service_job_events', 'marketplace', 'realtime',
   '{"append_only": true}'::jsonb,
   'Append-only job timeline written by the transition journaler - the record outlives the action.'),
  ('service_credit_ledger_raw', 'table', 'service_credit_ledger', 'marketplace', 'on_demand',
   '{"append_only": true, "balance": "SUM(amount) per account", "writes": "backend/GUC only - the trust-forge pattern extended to money"}'::jsonb,
   'Founder-income credit ledger. No client write path; non-withdrawable prepaid platform fees.'),
  ('service_credit_topups_raw', 'table', 'service_credit_topups', 'marketplace', 'on_demand',
   '{"key": ["gcash_ref"], "status_values": ["pending_verification", "verified", "rejected"], "verify": "founder/admin only; verification mints the ledger entry"}'::jsonb,
   'GCash P2P top-up filings awaiting founder verification against the personal GCash app.'),
  ('service_vouchers', 'table', 'service_vouchers', 'marketplace', 'on_demand',
   '{"key": ["code"], "redeem": "completion-gated via redeem_service_voucher(); per-user + max-use limits"}'::jsonb,
   'Founder-minted acquisition vouchers; platform-funded, reimbursed to the provider on a verified completion.'),
  ('service_voucher_redemptions', 'table', 'service_voucher_redemptions', 'marketplace', 'on_demand',
   '{"key": ["voucher_id", "request_id"], "writes": "RPC only"}'::jsonb,
   'Redemption records - written only by redeem_service_voucher() after a verified completion.'),
  -- ── Engine (views) ───────────────────────────────────────────────────────
  ('service_provider_truth', 'view', 'v_service_provider_truth', 'marketplace', 'realtime',
   '{"computed": ["completed_jobs", "rating_avg", "rating_count", "tier"], "privacy": "live_location deliberately ABSENT"}'::jsonb,
   'Provider directory truth: curated public columns + VIEW-COMPUTED trust (no forgeable stored counters).'),
  ('service_request_truth', 'view', 'v_service_request_truth', 'marketplace', 'realtime',
   '{"boundary": "own request as client, or matched provider via my_service_provider_ids()"}'::jsonb,
   'A party''s own requests with the matched provider folded in; the only client read path for a hail.'),
  ('service_open_broadcasts', 'view', 'v_service_open_broadcasts', 'marketplace', 'realtime',
   '{"scope": "category ∩ st_dwithin radius ∩ online provider identity"}'::jsonb,
   'A provider''s broadcast feed: open requests scoped to their categories and service radius.'),
  ('service_job_tracking', 'view', 'v_service_job_tracking', 'marketplace', 'realtime',
   '{"privacy": "the ONLY path to live_location, and only while the job is active"}'::jsonb,
   'Live tracking for an ACTIVE job: the client sees the matched provider''s position, nobody else does.'),
  ('service_catalog_truth', 'view', 'v_service_catalog_truth', 'marketplace', 'on_demand',
   '{"key": ["id"], "reason": "pages must not read the rate card raw (arc §1: Dashboard never reads Fuel)"}'::jsonb,
   'Rate-card truth view - the read path both the hail composer and provider onboarding use.'),
  ('service_credit_topups_truth', 'view', 'v_service_credit_topups_truth', 'marketplace', 'on_demand',
   '{"key": ["id"], "boundary": "payer_auth_uid = auth.uid() OR is_marketplace_admin() - re-asserted because the view is security_invoker=false"}'::jsonb,
   'GCash verification queue (admin) + a payer''s own filings, with the provider display name folded in.'),
  ('service_credit_ledger_truth', 'view', 'v_service_credit_ledger_truth', 'marketplace', 'on_demand',
   '{"key": ["id"], "append_only": true, "balance": "NOT from this view - provider_credit_balance() is the balance truth"}'::jsonb,
   'Credit ledger history for the owning account; display-only read path over the append-only money ledger.'),
  -- ── Engine (RPCs) ────────────────────────────────────────────────────────
  ('accept_service_request', 'rpc', 'accept_service_request', 'marketplace', 'on_demand',
   '{"atomic": "guarded UPDATE - exactly one winner per hail", "refusals": ["lost_race_or_closed", "no_online_provider_identity", "category_mismatch", "out_of_radius", "own_request", "insufficient_credits"]}'::jsonb,
   'First-accept-wins dispatch. Returns a reason instead of raising, so the console can explain the refusal.'),
  ('submit_service_quote', 'rpc', 'submit_service_quote', 'marketplace', 'on_demand',
   '{"one_per_provider_per_request": true}'::jsonb,
   'Quote-mode response from a provider whose categories and radius cover the request.'),
  ('select_quote', 'rpc', 'select_quote', 'marketplace', 'on_demand',
   '{"client_only": true, "effect": "selects one offer, declines the rest, moves the request to accepted"}'::jsonb,
   'The client picks a quote; the transition runs through the same state-machine guard.'),
  ('my_service_provider_ids', 'rpc', 'my_service_provider_ids', 'marketplace', 'on_demand',
   '{"security": "DEFINER identity helper - resolves provider ids for RLS without a column-restricted subquery"}'::jsonb,
   'Identity helper mirroring user_hive_ids(): the provider ids the caller owns (freelancer or hive company).'),
  ('provider_credit_balance', 'rpc', 'provider_credit_balance', 'marketplace', 'on_demand',
   '{"definition": "SUM(service_credit_ledger.amount) for the provider account"}'::jsonb,
   'Balance truth for the wallet + the accept-time debt gate. Never a stored column.'),
  ('redeem_service_voucher', 'rpc', 'redeem_service_voucher', 'marketplace', 'on_demand',
   '{"gates": ["verified completion", "per-user limit", "max uses", "expiry", "segment"], "effect": "reimburses the provider in credits"}'::jsonb,
   'Completion-gated voucher redemption; the platform absorbs the discount so the provider stays whole.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind,
      source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill,
      freshness   = EXCLUDED.freshness,
      contract    = EXCLUDED.contract,
      description = EXCLUDED.description;

COMMIT;
