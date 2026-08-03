-- Four objects shipped without a registry entry, so nothing knew where the credit numbers come from.
--
-- The canonical-anchor gate caught it: fuel 5 -> 8 un-anchored, engine 2 -> 3. Every new TABLE must be
-- registered in canonical_sources (the "fuel" layer) and every new v_*_truth view or get_* RPC must be
-- registered too (the "engine" layer). That is not bookkeeping for its own sake: the registry is what
-- lets a page declare its provenance in a source chip, what the drift miner reads to tell a raw base-table
-- read from a sanctioned one, and what a future reader consults to answer "which of these numbers is THE
-- number". An unregistered table is a number with no stated origin.
--
-- Registering them here rather than editing migrations 05/07/10/12, which are committed: rewriting a
-- shipped migration makes a restore diverge from prod.
--
-- ONE ROW PER DOMAIN. canonical_sources' PRIMARY KEY is (domain) ALONE, so `domain` is the per-object key
-- and not a grouping label -- the existing rows show the convention (domain 'service_catalog' holding
-- source_name 'service_catalog'). A first pass filed all four of these under a shared domain
-- 'credit_economy' with ON CONFLICT DO NOTHING, and three rows vanished without a word: psql reported
-- INSERT 0 1 for a four-row VALUES list. ON CONFLICT DO NOTHING is exactly as quiet as it says it is, so
-- it belongs only where a collision is genuinely expected. DO UPDATE here, so a re-run corrects a row
-- rather than skipping it.

insert into public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values
  ('credit_treasury', 'table', 'credit_treasury', 'marketplace', 'on_demand',
   '{"key": ["id"], "singleton": true, "invariant": "issued_credits <= authorised_credits"}'::jsonb,
   'THE SUPPLY. One row (id = 1): authorised_credits = 10,000,000 (1 credit = PHP1, so PHP10M is the '
   'lifetime liability ceiling) and issued_credits. A CHECK enforces issued <= authorised, and the only '
   'writers are issue_credits()/retire_credits(), both with EXECUTE revoked from clients. Read through '
   'v_credit_posture, never raw.'),

  ('credit_reservations', 'table', 'credit_reservations', 'marketplace', 'on_demand',
   '{"key": ["id"], "states": ["held", "released_to_buyer", "returned"]}'::jsonb,
   'One row per live listing holding 10% of its price in the seller''s credits. RETURNED IN FULL on '
   'delist or draft, which is the whole difference between this and the listing fee that was rejected in '
   'July: a fee is consumed whether or not the item sells, a reservation costs only locked working '
   'capital. Released to the buyer on sale by grant_listing_reward().'),

  ('credit_starter_grants', 'table', 'credit_starter_grants', 'marketplace', 'on_demand',
   '{"key": ["auth_uid"], "once_per_person": true}'::jsonb,
   'One starter grant per verified provider, ever - keyed on auth_uid so the uniqueness is structural '
   'rather than checked. Simulation put it as the single largest lever measured (cold-start throughput '
   'roughly doubled, and STALLED markets went to zero), which is why it exists; gated on identity '
   'verification, because an ungated grant is free fuel for Sybil accounts.'),

  ('v_credit_posture', 'view', 'v_credit_posture', 'marketplace', 'on_demand',
   '{"derived_from": ["pg_proc", "pg_trigger", "credit_treasury"], "security_invoker": true}'::jsonb,
   'THE ENGINE VIEW for the credit economy, and the read path for the supply figures. Derives the posture '
   'from the LIVE CATALOGUE rather than documentation: no cash-out function exists, the transfer guard is '
   'installed, the supply and issuance, and pesos_per_credit = 1.00 fixed. Those facts are what keep '
   'credits a closed-loop prepaid instrument rather than e-money or a security, so they are asserted by '
   'validate_credit_posture.py instead of trusted.')
on conflict (domain) do update set
  source_kind = excluded.source_kind,
  source_name = excluded.source_name,
  owner_skill = excluded.owner_skill,
  freshness   = excluded.freshness,
  contract    = excluded.contract,
  description = excluded.description;

-- the shared-domain row the first pass left behind
delete from public.canonical_sources
 where domain = 'credit_economy' and source_name = 'credit_treasury';
