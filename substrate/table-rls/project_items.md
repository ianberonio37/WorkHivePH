---
name: table-rls-project_items
type: table-rls
source: db:pg_policies+pg_trigger:project_items
source_sha: c5b72ec46c7ec0e2
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `project_items` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, project_id*, hive_id*, wbs_code, title*, owner_name, status*, pct_complete*, planned_start, planned_end, predecessors*, estimated_hours, actual_hours, notes, sort_order*, created_at*, updated_at*, actual_start, actual_end

Policies:
- `project_items_hive_rw` [ALL · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`
- `project_items_parent_hive_guard` [ALL · roles=public] USING=`true` CHECK=`((( SELECT auth.uid() AS uid) IS NULL) OR (project_id IS NULL) OR (EXISTS ( SELECT 1 FROM projects p WHERE ((p.id = proj`

Guard triggers: `trg_daily_cap_project_items`, `trg_text_caps_project_items`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
