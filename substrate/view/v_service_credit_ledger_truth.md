---
name: view-v_service_credit_ledger_truth
type: view
source: db:pg_get_viewdef:v_service_credit_ledger_truth
source_sha: 21c4ee4519f5f90c
last_verified: 2026-07-13
supersedes: null
---
## view · `v_service_credit_ledger_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `service_credit_ledger`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id, account_type, account_id, entry_type, amount, ref_kind, ref_id, note, created_at, 1 AS _source_count, created_at AS _freshness_ts, 'service_credit_ledger_truth:v1'::text AS _canonical_version FROM service_credit_ledger l WHERE (((account_type = 'consumer'::text) AND (account_id = auth.uid())) OR ((account_type = 'provider'::text) AND (account_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids))) OR is_marketplace_admin());

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
