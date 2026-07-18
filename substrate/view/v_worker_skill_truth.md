---
name: view-v_worker_skill_truth
type: view
source: db:pg_get_viewdef:v_worker_skill_truth
source_sha: 56fe15fd98abeeff
last_verified: 2026-07-13
supersedes: null
---
## view · `v_worker_skill_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `hive_members`, `levels_per_discipline`, `skill_badges`, `skill_profiles`
**Trust/identity cols exposed:** `current_level`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  WITH worker_in_hive AS ( SELECT hm.hive_id, hm.worker_name, hm.role, hm.auth_uid, hm.joined_at FROM hive_members hm WHERE (hm.status = 'active'::text) ), levels_per_discipline AS ( SELECT skill_badges.worker_name, skill_badges.discipline, max(skill_badges.level) AS current_level, count(*) AS badge_count, max(skill_badges.earned_at) AS last_earned_at FROM skill_badges WHERE ((skill_badges.level >= 1) AND (skill_badges.level <= 5)) GROUP BY skill_badges.worker_name, skill_badges.discipline ) SELECT wih.hive_id, wih.worker_name, wih.role, wih.auth_uid, wih.joined_at, sp.primary_skill, lpd.discip …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
