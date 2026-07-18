---
name: view-v_session_memory_recent
type: view
source: db:pg_get_viewdef:v_session_memory_recent
source_sha: fd70e9a913bb0f03
last_verified: 2026-07-13
supersedes: null
---
## view · `v_session_memory_recent`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `agent_memory`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT session_id, turn_num, user_input, assistant_response, intent_classification, intent_confidence, response_time_ms, created_at FROM agent_memory ORDER BY turn_num DESC LIMIT 10;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
