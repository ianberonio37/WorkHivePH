---
name: view-v_worker_achievements
type: view
source: db:pg_get_viewdef:v_worker_achievements
source_sha: 5daf1562f648137d
last_verified: 2026-07-13
supersedes: null
---
## view · `v_worker_achievements`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `worker_achievements`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id, worker_name, achievement_id, current_level, xp_total, last_action_at FROM worker_achievements;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
