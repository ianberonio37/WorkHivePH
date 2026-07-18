---
name: view-v_pf_truth
type: view
source: db:pg_get_viewdef:v_pf_truth
source_sha: 4f1ddeebb5ec460a
last_verified: 2026-07-13
supersedes: null
---
## view · `v_pf_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `pf_intervals`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT DISTINCT ON (hive_id, asset_id, parameter, COALESCE((fmea_mode_id)::text, '_'::text)) id AS pf_interval_id, hive_id, asset_id, fmea_mode_id, parameter, p_threshold, f_threshold, pf_days, recommended_interval_days, basis, generated_at FROM pf_intervals ORDER BY hive_id, asset_id, parameter, COALESCE((fmea_mode_id)::text, '_'::text), generated_at DESC;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
