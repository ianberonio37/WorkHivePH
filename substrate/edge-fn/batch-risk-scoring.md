---
name: edge-fn-batch-risk-scoring
type: edge-fn
source: file:supabase/functions/batch-risk-scoring/index.ts
source_sha: 309f18268347cf57
last_verified: 2026-07-13
supersedes: null
---
## edge-fn · `batch-risk-scoring` (supabase/functions/batch-risk-scoring)

Auth gate: **auth idiom detected in body (verify it gates the hive_id it uses)**

Tables touched: `asset_risk_scores`, `automation_log`, `pm_completions`, `v_asset_truth`, `v_fmea_truth`, `v_hives_truth`, `v_inventory_items_truth`, `v_inventory_transactions_truth`, `v_logbook_truth`, `v_pm_compliance_truth`, `v_pm_scope_items_truth`, `v_weibull_truth`, `v_worker_truth`
RPCs called: `get_mtbf_by_machine`

Links: [[project_platform_knowledge_substrate]]
