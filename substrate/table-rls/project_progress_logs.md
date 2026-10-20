---
name: table-rls-project_progress_logs
type: table-rls
source: db:pg_policies+pg_trigger:project_progress_logs
source_sha: 3d611440d04afd77
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `project_progress_logs` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, project_id*, hive_id*, log_date*, reported_by*, pct_complete*, hours_worked, notes, blockers, acknowledged_by, acknowledged_at, created_at*, auth_uid

Policies:
- `project_progress_logs_hive_rw` [ALL · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`
- `project_progress_logs_parent_hive_guard` [ALL · roles=public] USING=`true` CHECK=`((( SELECT auth.uid() AS uid) IS NULL) OR (project_id IS NULL) OR (EXISTS ( SELECT 1 FROM projects p WHERE ((p.id = proj`

Guard triggers: `trg_bind_progress_log_submitter`, `trg_daily_cap_project_progress`, `trg_text_caps_project_progress`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
