---
name: table-rls-tts_cache
type: table-rls
source: db:pg_policies+pg_trigger:tts_cache
source_sha: 772de92a3fc7d83c
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `tts_cache` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, text_hash*, text_content*, persona*, duration_ms, created_at, expires_at

Policies: (none)

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
