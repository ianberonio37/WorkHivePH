---
name: view-v_external_sync_truth
type: view
source: db:pg_get_viewdef:v_external_sync_truth
source_sha: 42e48f15805dd58b
last_verified: 2026-07-13
supersedes: null
---
## view · `v_external_sync_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `external_sync`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id, hive_id, system_type, external_id, entity_type, workhive_table, status, sync_payload, last_synced_at, sync_status, (sync_status = 'active'::text) AS is_active, (sync_status = 'deleted'::text) AS is_deleted, (sync_status = 'error'::text) AS is_error, (last_synced_at >= (now() - '24:00:00'::interval)) AS synced_within_24h, (last_synced_at >= (now() - '7 days'::interval)) AS synced_within_7d, ((now())::date - (last_synced_at)::date) AS days_since_sync FROM external_sync e;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
