---
name: view-v_service_credit_topups_truth
type: view
source: db:pg_get_viewdef:v_service_credit_topups_truth
source_sha: ca3bdc019cbbcf40
last_verified: 2026-07-13
supersedes: null
---
## view · `v_service_credit_topups_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `service_providers`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT t.id, t.account_type, t.account_id, t.payer_auth_uid, t.amount, t.gcash_ref, t.status, t.verified_at, t.verified_by, t.note, t.created_at, sp.display_name AS provider_display_name, 1 AS _source_count, t.created_at AS _freshness_ts, 'service_credit_topups_truth:v1'::text AS _canonical_version FROM (service_credit_topups t LEFT JOIN service_providers sp ON (((t.account_type = 'provider'::text) AND (sp.id = t.account_id)))) WHERE ((t.payer_auth_uid = auth.uid()) OR is_marketplace_admin());

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
