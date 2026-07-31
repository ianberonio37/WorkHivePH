-- 20260731000023_anchor_the_four_new_tables.sql
--
-- REGISTRATION CASCADE, Fuel layer. The canonical-anchor gate counts un-anchored tables and it went 5 -> 9:
-- every new table must declare, in `canonical_sources`, what it IS and what its write contract is. Four had
-- landed without it — `service_payments` from today's money arc, and `hive_service_settings`,
-- `embedding_outbox` and `embedding_registry` from earlier arcs that shipped the table but skipped the
-- anchor. (The same four were also missing from reset.py, caught by a different gate an hour earlier — a
-- new table has more than one place it has to be declared, and neither gate knows about the other.)
--
-- The `contract` is the load-bearing field: it is where a future reader learns that service_payments is
-- RECORD-ONLY and immutable, which is the whole basis of the platform's regulatory posture.
insert into public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values
  ('service_payments_raw', 'table', 'service_payments', 'marketplace', 'on_demand',
   '{"writes": "the CLIENT attests, once, via RLS insert; no UPDATE or DELETE policy exists",
     "immutable": true, "one_per_request": true,
     "custody": "NONE - records a payment made DIRECTLY between two other parties (D13)",
     "billed_against": "commission and cashback both read amount_paid"}'::jsonb,
   'Record-only attestation that a consumer paid a provider directly. The platform never holds these '
   'funds; this row is what commission is billed against and what a dispute argues about. Its immutability '
   'is why it can serve as evidence.'),

  ('hive_service_settings_raw', 'table', 'hive_service_settings', 'marketplace', 'on_demand',
   '{"writes": "hive admin", "resolver": "service_knob() / service_knob_pct() - never read raw",
     "tighten_only": "trust thresholds carry CHECK floors (silver>=11, gold>=51, gold>silver) so a hive may make its OWN sellers work harder, never easier",
     "solvency": "CHECK refuses cashback_pct > commission_pct + listing_fee_pct"}'::jsonb,
   'Per-hive D9 knobs: hail timing and reach, trust thresholds, and the credit rates (commission, cashback, '
   'listing fee, min list balance). Read through the resolver, which falls back to platform defaults.'),

  ('embedding_outbox_raw', 'table', 'embedding_outbox', 'ai-engineer', 'realtime',
   '{"writes": "triggers enqueue; the drainer claims with FOR UPDATE SKIP LOCKED",
     "lease": "claimed_at visibility lease with exponential backoff and a dead-letter",
     "transient": true}'::jsonb,
   'Transactional outbox for the auto-embed spine: a row enqueued in the same transaction as its source, so '
   'an embedding can never be silently lost when the embedder is down.'),

  ('embedding_registry_raw', 'table', 'embedding_registry', 'ai-engineer', 'on_demand',
   '{"writes": "backend only", "one_model_per_corpus": "a corpus split across models is not a degraded index, it is a silently broken one"}'::jsonb,
   'Which model owns which corpus. Exists because cosine against a foreign geometry returns noise rather '
   'than a worse answer, so a mixed-model corpus fails invisibly.')
on conflict do nothing;
