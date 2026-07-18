---
name: view-v_dialog_state_current
type: view
source: db:pg_get_viewdef:v_dialog_state_current
source_sha: 0a4cb807acafbec5
last_verified: 2026-07-13
supersedes: null
---
## view · `v_dialog_state_current`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `dialog_state`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT session_id, current_intent, intent_confidence, context_slots, clarification_pending, clarification_prompt, last_turn_num FROM dialog_state WHERE (updated_at > (now() - '01:00:00'::interval));

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
