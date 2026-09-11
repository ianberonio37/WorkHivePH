---
name: table-rls-tts_cache
type: table-rls
source: db:pg_policies+pg_trigger:tts_cache
source_sha: b7ab7531c34e8c0c
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `tts_cache` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **False** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, text_hash*, text_content*, persona*, duration_ms, created_at, expires_at

Policies: (none)

**Verdict:** FLAGS: RLS-DISABLED — world-open unless anon grants are revoked (audit has_table_privilege).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
