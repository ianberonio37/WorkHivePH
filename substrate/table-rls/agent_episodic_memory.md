---
name: table-rls-agent_episodic_memory
type: table-rls
source: db:pg_policies+pg_trigger:agent_episodic_memory
source_sha: c0df99c8b7ed45f2
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `agent_episodic_memory` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id, worker_name, auth_uid, memory_type*, content*, embedding, importance*, use_count*, last_used_at, source_trace_id, created_at*, superseded_by, superseded_at

Policies:
- `aem_insert` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `aem_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))` CHECK=`∅`
- `aem_update` [UPDATE · roles=public] USING=`false` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
