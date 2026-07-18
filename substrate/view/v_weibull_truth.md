---
name: view-v_weibull_truth
type: view
source: db:pg_get_viewdef:v_weibull_truth
source_sha: c60f3a60a6d01818
last_verified: 2026-07-13
supersedes: null
---
## view · `v_weibull_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `weibull_fits`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT DISTINCT ON (hive_id, asset_id, COALESCE((fmea_mode_id)::text, '_'::text)) id AS fit_id, hive_id, asset_id, fmea_mode_id, beta, eta_days, failure_pattern, n_failures, n_censored, fit_method, log_likelihood, source_window_days, generated_at FROM weibull_fits ORDER BY hive_id, asset_id, COALESCE((fmea_mode_id)::text, '_'::text), generated_at DESC;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
