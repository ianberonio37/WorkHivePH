---
name: view-v_project_progress_truth
type: view
source: db:pg_get_viewdef:v_project_progress_truth
source_sha: 058519ac889de28b
last_verified: 2026-07-13
supersedes: null
---
## view · `v_project_progress_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `pl`, `projects`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT pl.id, pl.project_id, pl.hive_id, pl.log_date, pl.reported_by, pl.pct_complete, pl.hours_worked, pl.notes, pl.blockers, pl.acknowledged_by, pl.acknowledged_at, pl.created_at, p.name AS project_name, p.project_code, p.status AS project_status, (pl.acknowledged_at IS NOT NULL) AS is_acknowledged, ((pl.blockers IS NOT NULL) AND (length(TRIM(BOTH FROM pl.blockers)) > 0)) AS has_blocker, ((now())::date - pl.log_date) AS days_since_log FROM (project_progress_logs pl LEFT JOIN projects p ON ((p.id = pl.project_id)));

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
