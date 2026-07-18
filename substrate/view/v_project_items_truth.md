---
name: view-v_project_items_truth
type: view
source: db:pg_get_viewdef:v_project_items_truth
source_sha: 035ca02b0d1cab04
last_verified: 2026-07-13
supersedes: null
---
## view · `v_project_items_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `projects`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT i.id, i.project_id, i.hive_id, i.wbs_code, i.title, i.owner_name, i.status, i.pct_complete, i.planned_start, i.planned_end, i.actual_start, i.actual_end, i.predecessors, i.estimated_hours, i.actual_hours, i.notes, i.sort_order, i.created_at, i.updated_at, p.name AS project_name, p.project_code, p.status AS project_status, (i.status = 'pending'::text) AS is_pending, (i.status = 'in_progress'::text) AS is_in_progress, (i.status = 'done'::text) AS is_done, (i.status = 'blocked'::text) AS is_blocked, (i.status = 'skipped'::text) AS is_skipped, ((i.planned_end IS NOT NULL) AND (i.planned_en …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
