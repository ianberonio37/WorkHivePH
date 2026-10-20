---
name: table-rls-embedding_cache
type: table-rls
source: db:pg_policies+pg_trigger:embedding_cache
source_sha: 8b1516c4acf0e02b
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `embedding_cache` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): query_hash*, model*, embedding*, hits*, created_at*, last_used*

Policies: (none)

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
