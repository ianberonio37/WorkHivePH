---
name: view-v_project_truth
type: view
source: db:pg_get_viewdef:v_project_truth
source_sha: 720f502d19c3a763
last_verified: 2026-07-13
supersedes: null
---
## view · `v_project_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `project_change_orders`, `project_items`, `project_links`, `project_progress_logs`, `projects`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id AS project_id, hive_id, project_code, name, project_type, status, priority, owner_name, budget_php, start_date, end_date AS target_end_date, closed_at AS actual_end_at, created_at, updated_at, ( SELECT count(*) AS count FROM project_items pi WHERE (pi.project_id = p.id)) AS item_count, ( SELECT count(*) AS count FROM project_items pi WHERE ((pi.project_id = p.id) AND (pi.status = 'done'::text))) AS items_done, ( SELECT COALESCE(sum(pi.estimated_hours), (0)::numeric) AS "coalesce" FROM project_items pi WHERE (pi.project_id = p.id)) AS estimated_total_hours, ( SELECT COALESCE(sum(pi.a …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
