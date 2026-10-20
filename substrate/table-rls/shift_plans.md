---
name: table-rls-shift_plans
type: table-rls
source: db:pg_policies+pg_trigger:shift_plans
source_sha: e9377ed88ba319e8
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `shift_plans` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, shift_window*, shift_date*, status*, generated_at*, generated_by*, published_at, published_by, briefing, payload*, created_at*, updated_at*

Policies:
- `shift_plans_supervisor_write` [ALL · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = shift_plans.` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid `
- `shift_plans_read` [SELECT · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid ` CHECK=`∅`

Guard triggers: `trg_bind_shift_plan_publisher`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
