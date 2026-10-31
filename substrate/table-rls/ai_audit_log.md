---
name: table-rls-ai_audit_log
type: table-rls
source: db:pg_policies+pg_trigger:ai_audit_log
source_sha: a7f68eefdfd93195
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ai_audit_log` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, worker_name, event*, payload*, source, created_at

Policies:
- `ai_audit_log_hive_insert` [INSERT · roles=authenticated] USING=`∅` CHECK=`((hive_id IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = ai_audit_log.hive_id) AND (hm.au`
- `ai_audit_log_hive_select` [SELECT · roles=authenticated] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (is_platform_admin() OR ((hive_id IS NOT NULL) AND (EXISTS ( SELECT 1 FRO` CHECK=`∅`

Guard triggers: `trg_bind_ai_audit_log_actor`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
