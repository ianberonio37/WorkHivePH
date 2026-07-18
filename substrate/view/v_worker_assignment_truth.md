---
name: view-v_worker_assignment_truth
type: view
source: db:pg_get_viewdef:v_worker_assignment_truth
source_sha: 6b6437f79dca7119
last_verified: 2026-07-13
supersedes: null
---
## view · `v_worker_assignment_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `logbook`, `pm_completions`, `recent_logbook`, `recent_pm`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  WITH recent_logbook AS ( SELECT logbook.hive_id, logbook.worker_name, count(*) AS jobs_30d, count(*) FILTER (WHERE (logbook.status = ANY (ARRAY['Open'::text, 'In Progress'::text]))) AS open_jobs, max(logbook.created_at) AS last_job_at, count(DISTINCT logbook.asset_node_id) AS assets_touched_30d, sum(COALESCE(logbook.downtime_hours, (0)::numeric)) AS total_downtime_hours_30d, (array_agg(logbook.category ORDER BY logbook.created_at DESC))[1] AS last_category FROM logbook WHERE (logbook.created_at >= (now() - '30 days'::interval)) GROUP BY logbook.hive_id, logbook.worker_name ), recent_pm AS ( S …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
