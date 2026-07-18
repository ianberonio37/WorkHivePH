---
name: view-v_rcm_truth
type: view
source: db:pg_get_viewdef:v_rcm_truth
source_sha: 9837d0dbf4b2bfb5
last_verified: 2026-07-13
supersedes: null
---
## view · `v_rcm_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `rcm_fmea_modes`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT s.id AS strategy_id, s.hive_id, s.fmea_mode_id, m.asset_id, s.decision, s.task_text, s.interval_days, s.rationale, s.weibull_fit_id, s.pf_interval_id, s.written_to_pm_scope_item_id, s.source, s.ai_confidence, s.created_at, s.updated_at, s.approved_at FROM (rcm_strategies s JOIN rcm_fmea_modes m ON ((m.id = s.fmea_mode_id))) WHERE (s.approved_at IS NOT NULL);

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
