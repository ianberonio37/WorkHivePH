---
name: view-v_worker_truth
type: view
source: db:pg_get_viewdef:v_worker_truth
source_sha: 76c2e171bbd76055
last_verified: 2026-07-13
supersedes: null
---
## view · `v_worker_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `hive_members`
**Trust/identity cols exposed:** `worker_name`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT wp.auth_uid, wp.username, wp.display_name AS worker_name, wp.email, wp.preferred_persona, wp.created_at AS registered_at, hm.hive_id, hm.role, hm.joined_at AS hive_joined_at, hm.status AS hive_status, (hm.hive_id IS NULL) AS is_solo, ( SELECT count(*) AS count FROM hive_members hm2 WHERE ((hm2.worker_name = wp.display_name) AND (hm2.status = 'active'::text))) AS active_hive_count FROM (worker_profiles wp LEFT JOIN hive_members hm ON (((hm.worker_name = wp.display_name) AND (hm.status = 'active'::text))));

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
