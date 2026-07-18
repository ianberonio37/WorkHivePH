---
name: view-v_worker_achievements_truth
type: view
source: db:pg_get_viewdef:v_worker_achievements_truth
source_sha: 7fd5753a6ed3a00e
last_verified: 2026-07-13
supersedes: null
---
## view · `v_worker_achievements_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `achievement_definitions`, `worker_profiles`
**Trust/identity cols exposed:** `xp_into_current_level`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT wa.id, wa.auth_uid, wa.worker_name, wa.achievement_id, wa.current_level, wa.xp_total, wa.last_action_at, ad.name AS achievement_name, ad.description AS achievement_description, ad.xp_per_level, ad.max_level, wp.display_name AS worker_display_name, (wa.current_level >= ad.max_level) AS is_maxed, CASE WHEN (ad.xp_per_level > 0) THEN ((wa.xp_total - (wa.current_level * ad.xp_per_level)))::integer ELSE 0 END AS xp_into_current_level, CASE WHEN ((ad.xp_per_level > 0) AND (wa.current_level < ad.max_level)) THEN ((((wa.current_level + 1) * ad.xp_per_level) - wa.xp_total))::integer ELSE 0 END  …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
