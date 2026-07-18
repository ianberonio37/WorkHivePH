---
name: table-rls-mfa_enrollments
type: table-rls
source: db:pg_policies+pg_trigger:mfa_enrollments
source_sha: e63b7b2b230c1ad7
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `mfa_enrollments` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): id*, auth_uid*, worker_name, last_verified_at, notes

Policies:
- `mfa_enrollments_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `mfa_enrollments_read` [SELECT · roles=public] USING=`(auth.uid() = auth_uid)` CHECK=`∅`
- `mfa_enrollments_update_locked` [UPDATE · roles=public] USING=`false` CHECK=`false`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
