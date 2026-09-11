---
name: table-rls-embedding_registry
type: table-rls
source: db:pg_policies+pg_trigger:embedding_registry
source_sha: c7ad5f57c70bece6
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `embedding_registry` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): source_table*, target_table*, conflict_key*, min_chars*, embedding_model*, text_fields*, visibility*, active*, created_at*

Policies: (none)

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
