---
name: table-rls-projects
type: table-rls
source: db:pg_policies+pg_trigger:projects
source_sha: 16cfe949b68aa5f7
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `projects` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id*, worker_name*, auth_uid, project_code*, name*, project_type*, status*, priority*, owner_name, description, start_date, end_date, budget_php, meta*, created_at*, updated_at*, closed_at, deleted_at

Policies:
- `projects_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

Guard triggers: `trg_bind_submitter_projects`, `trg_daily_cap_projects`, `trg_text_caps_projects`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
