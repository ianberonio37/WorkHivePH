---
name: view-v_amc_truth
type: view
source: db:pg_get_viewdef:v_amc_truth
source_sha: 89ae6e1080220be8
last_verified: 2026-07-13
supersedes: null
---
## view · `v_amc_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `amc_briefings`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT DISTINCT ON (hive_id, shift_date) id AS amc_id, hive_id, shift_date, generated_at, status, asset_count, pm_count, parts_count, COALESCE((brief ->> 'summary'::text), (brief ->> 'composer_summary'::text), ''::text) AS summary, COALESCE((brief ->> 'headline'::text), (brief ->> 'composer_headline'::text), ''::text) AS headline, approved_by, approved_at, expires_at, model_version FROM amc_briefings a ORDER BY hive_id, shift_date, generated_at DESC;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
