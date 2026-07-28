---
name: table-rls-project_progress_logs
type: table-rls
source: db:pg_policies+pg_trigger:project_progress_logs
source_sha: 4f8046e04b043c9f
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `project_progress_logs` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, project_id*, hive_id*, log_date*, reported_by*, pct_complete*, hours_worked, notes, blockers, acknowledged_by, acknowledged_at, created_at*, auth_uid

Policies:
- `project_progress_logs_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`
- `project_progress_logs_parent_hive_guard` [ALL · roles=public] USING=`true` CHECK=`((auth.uid() IS NULL) OR (project_id IS NULL) OR (EXISTS ( SELECT 1 FROM projects p WHERE ((p.id = project_progress_logs`

Guard triggers: `trg_daily_cap_project_progress`, `trg_text_caps_project_progress`

**Verdict:** FLAGS: has auth_uid + a CLIENT-WRITABLE policy that does NOT self-pin auth_uid AND no bind_* trigger — ATTRIBUTION-FORGERY suspect.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
