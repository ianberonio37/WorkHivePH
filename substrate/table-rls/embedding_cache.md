---
name: table-rls-embedding_cache
type: table-rls
source: db:pg_policies+pg_trigger:embedding_cache
source_sha: 3602197639728d34
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `embedding_cache` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **False** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): query_hash*, model*, embedding*, hits*, created_at*, last_used*

Policies: (none)

**Verdict:** FLAGS: RLS-DISABLED — world-open unless anon grants are revoked (audit has_table_privilege).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
