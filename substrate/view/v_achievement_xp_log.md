---
name: view-v_achievement_xp_log
type: view
source: db:pg_get_viewdef:v_achievement_xp_log
source_sha: c62d6225a9afe40a
last_verified: 2026-07-13
supersedes: null
---
## view · `v_achievement_xp_log`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `achievement_xp_log`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id, worker_name, achievement_id, xp_earned, source_action, source_id, earned_at FROM achievement_xp_log;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
