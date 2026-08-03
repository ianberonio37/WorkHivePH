---
name: view-v_gcash_receipts_needing_eyes
type: view
source: db:pg_get_viewdef:v_gcash_receipts_needing_eyes
source_sha: bd4803c1c58e56b2
last_verified: 2026-07-13
supersedes: null
---
## view · `v_gcash_receipts_needing_eyes`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `gcash_inbound_receipts`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id, reference, amount, sender_name, received_at, match_state, match_note, created_at FROM gcash_inbound_receipts r WHERE (match_state <> 'matched'::text) ORDER BY created_at DESC;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
