---
name: table-rls-project_roles
type: table-rls
source: db:pg_policies+pg_trigger:project_roles
source_sha: d651f75a305a5789
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `project_roles` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, project_id*, hive_id*, worker_name*, role*, assigned_by, assigned_at*, notes, deleted_at, deleted_by

Policies:
- `project_roles_supervisor_all` [ALL · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = project_role` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = project_role`
- `project_roles_hides_deleted` [SELECT · roles=public] USING=`((deleted_at IS NULL) OR ( SELECT wh_trash_scope() AS wh_trash_scope))` CHECK=`∅`
- `project_roles_project_member_read` [SELECT · roles=authenticated] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (project_id IN ( SELECT user_project_ids() AS user_project_ids)))` CHECK=`∅`

Guard triggers: `tg_guard_project_role_assignee`, `trg_text_caps_project_roles`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
