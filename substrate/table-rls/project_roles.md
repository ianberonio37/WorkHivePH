---
name: table-rls-project_roles
type: table-rls
source: db:pg_policies+pg_trigger:project_roles
source_sha: 77a4e9c4a8a91836
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `project_roles` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, project_id*, hive_id*, worker_name*, role*, assigned_by, assigned_at*, notes

Policies:
- `project_roles_supervisor_all` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = project_roles.hive_id) AND (h` CHECK=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = project_roles.hive_id) AND (h`

Guard triggers: `trg_text_caps_project_roles`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
