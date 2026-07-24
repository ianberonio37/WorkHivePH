---
name: edge-fn-analytics-orchestrator
type: edge-fn
source: file:supabase/functions/analytics-orchestrator/index.ts
source_sha: 3431538b5fae29a9
last_verified: 2026-07-13
supersedes: null
---
## edge-fn · `analytics-orchestrator` (supabase/functions/analytics-orchestrator)

Auth gate: **auth idiom detected in body (verify it gates the hive_id it uses)**

Tables touched: `analytics_snapshots`, `engineering_calcs`, `pm_assets`, `pm_completions`, `v_inventory_items_truth`, `v_inventory_transactions_truth`, `v_logbook_truth`, `v_pm_compliance_truth`, `v_pm_scope_items_truth`, `v_risk_truth`, `v_worker_skill_truth`, `v_worker_truth`, `worker_profiles`
RPCs called: `get_downtime_pareto`, `get_failure_frequency`, `get_mtbf_by_machine`, `get_mttr_by_machine`, `get_oee_by_machine`, `get_pm_compliance_smrp`, `get_repeat_failures`

Links: [[project_platform_knowledge_substrate]]
