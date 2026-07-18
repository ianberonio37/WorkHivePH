---
name: edge-fn-scheduled-agents
type: edge-fn
source: file:supabase/functions/scheduled-agents/index.ts
source_sha: 32b900265e906e3e
last_verified: 2026-07-13
supersedes: null
---
## edge-fn · `scheduled-agents` (supabase/functions/scheduled-agents)

Auth gate: **auth idiom detected in body (verify it gates the hive_id it uses)**

Tables touched: `ai_reports`, `automation_log`, `project_links`, `v_hives_truth`, `v_logbook_truth`, `v_pm_scope_items_truth`, `v_project_progress_truth`, `v_project_truth`
RPCs called: `get_failure_frequency`, `get_mtbf_by_machine`, `get_mttr_by_machine`, `get_repeat_failures`

Links: [[project_platform_knowledge_substrate]]
