---
name: view-v_asset_state_truth
type: view
source: db:pg_get_viewdef:v_asset_state_truth
source_sha: 5bcddf30cac88f58
last_verified: 2026-07-13
supersedes: null
---
## view · `v_asset_state_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `unified_events`
**Trust/identity cols exposed:** `verified_at`, `verified_payload`, `verified_source`, `verified_source_rank`, `verified_text`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT DISTINCT ON (hive_id, asset_tag, event_type) hive_id, asset_tag, event_type, source AS verified_source, unified_event_source_rank(source) AS verified_source_rank, source_id, occurred_at AS verified_at, payload AS verified_payload, payload_text AS verified_text, count(*) OVER (PARTITION BY hive_id, asset_tag, event_type) AS conflict_count, (count(*) OVER (PARTITION BY hive_id, asset_tag, event_type) - 1) AS superseded_count, ingested_at, count(*) OVER (PARTITION BY hive_id, asset_tag, event_type) AS _source_count, max(ingested_at) OVER (PARTITION BY hive_id, asset_tag, event_type) AS _f …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
