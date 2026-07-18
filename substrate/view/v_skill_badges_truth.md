---
name: view-v_skill_badges_truth
type: view
source: db:pg_get_viewdef:v_skill_badges_truth
source_sha: 980df07883a4c1b0
last_verified: 2026-07-13
supersedes: null
---
## view · `v_skill_badges_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `worker_profiles`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT b.id, b.worker_name, b.auth_uid, b.discipline, b.level, b.exam_score, b.earned_at, wp.display_name AS worker_display_name, wp.email AS worker_email, CASE b.level WHEN 1 THEN 'Trainee'::text WHEN 2 THEN 'Operator'::text WHEN 3 THEN 'Technician'::text WHEN 4 THEN 'Specialist'::text WHEN 5 THEN 'Master'::text ELSE 'Unknown'::text END AS level_label, (b.earned_at >= (now() - '30 days'::interval)) AS earned_recent FROM (skill_badges b LEFT JOIN worker_profiles wp ON ((wp.display_name = b.worker_name)));

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
