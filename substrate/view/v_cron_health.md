---
name: view-v_cron_health
type: view
source: db:pg_get_viewdef:v_cron_health
source_sha: cdd82a6cdf3063b5
last_verified: 2026-07-13
supersedes: null
---
## view · `v_cron_health`

**security_invoker:** OFF ⚠  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `cron`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT j.jobid, j.jobname, j.schedule, j.active, d.runid, d.status, d.start_time, d.end_time, "left"(d.return_message, 200) AS return_message FROM (cron.job j LEFT JOIN cron.job_run_details d ON ((d.jobid = j.jobid)));

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
