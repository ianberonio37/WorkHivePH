---
name: table-rls-persona_knowledge
type: table-rls
source: db:pg_policies+pg_trigger:persona_knowledge
source_sha: 53554e4fa724bd68
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `persona_knowledge` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **False** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, persona_scope*, source*, source_type*, section, chunk_index*, context_header, content*, content_hash*, embedding, embedding_model, created_at*, updated_at*

Policies: (none)

**Verdict:** FLAGS: RLS-DISABLED — world-open unless anon grants are revoked (audit has_table_privilege).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
