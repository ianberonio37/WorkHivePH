---
name: view-v_ai_reports_truth
type: view
source: db:pg_get_viewdef:v_ai_reports_truth
source_sha: c2182e06f7261867
last_verified: 2026-07-13
supersedes: null
---
## view · `v_ai_reports_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `ai_reports`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id, hive_id, report_type, generated_at, report_json, summary, created_at, (EXTRACT(epoch FROM (now() - generated_at)) / 3600.0) AS hours_since_generated, (generated_at >= (now() - '24:00:00'::interval)) AS fresh_24h, (generated_at >= (now() - '08:00:00'::interval)) AS fresh_8h, (report_type = 'pm_overdue'::text) AS is_pm_overdue, (report_type = 'failure_digest'::text) AS is_failure_digest, (report_type = 'shift_handover'::text) AS is_shift_handover, (report_type = 'predictive'::text) AS is_predictive FROM ai_reports r;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
