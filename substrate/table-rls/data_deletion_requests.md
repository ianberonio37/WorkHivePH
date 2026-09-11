---
name: table-rls-data_deletion_requests
type: table-rls
source: db:pg_policies+pg_trigger:data_deletion_requests
source_sha: 537e08cab736a1e9
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `data_deletion_requests` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, auth_uid*, worker_name*, hive_id, scope*, reason, status*, requested_at*, resolved_at, resolution

Policies:
- `ddr_own_insert` [INSERT · roles=authenticated] USING=`∅` CHECK=`(auth_uid = auth.uid())`
- `ddr_own_read` [SELECT · roles=authenticated] USING=`(auth_uid = auth.uid())` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
