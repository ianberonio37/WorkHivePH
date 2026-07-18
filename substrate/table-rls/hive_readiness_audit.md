---
name: table-rls-hive_readiness_audit
type: table-rls
source: db:pg_policies+pg_trigger:hive_readiness_audit
source_sha: b12ca587db3b840a
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_readiness_audit` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, reason, changed_at*, previous_stair, new_stair, previous_composite, new_composite, evidence_delta

Policies:
- `hive_readiness_audit_write_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `hive_readiness_audit_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
