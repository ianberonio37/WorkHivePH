---
name: view-v_adoption_truth
type: view
source: db:pg_get_viewdef:v_adoption_truth
source_sha: a46944ed9e81f9b3
last_verified: 2026-07-13
supersedes: null
---
## view · `v_adoption_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `hive_adoption_score`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT hive_id, snapshot_date, risk_score, risk_tier, active_ratio_risk, momentum_risk, supervisor_decay_risk, stair_stall_risk, new_worker_silence_risk, top_reasons, champion_candidate, champion_engagement, dropping_workers, computed_at, model_version FROM hive_adoption_score has WHERE (snapshot_date = ( SELECT max(hive_adoption_score.snapshot_date) AS max FROM hive_adoption_score WHERE (hive_adoption_score.hive_id = has.hive_id)));

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
