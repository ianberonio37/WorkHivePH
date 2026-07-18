---
name: table-rls-project_progress_logs
type: table-rls
source: db:pg_policies+pg_trigger:project_progress_logs
source_sha: e4775734d046a81e
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `project_progress_logs` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, project_id*, hive_id*, log_date*, reported_by*, pct_complete*, hours_worked, notes, blockers, acknowledged_by, acknowledged_at, created_at*

Policies:
- `project_progress_logs_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

Guard triggers: `trg_daily_cap_project_progress`, `trg_text_caps_project_progress`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
