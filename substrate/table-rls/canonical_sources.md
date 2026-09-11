---
name: table-rls-canonical_sources
type: table-rls
source: db:pg_policies+pg_trigger:canonical_sources
source_sha: 6815ea2a102ee211
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `canonical_sources` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): domain*, source_kind*, source_name*, owner_skill*, freshness*, contract*, description*, registered_at*, last_validated, notes

Policies:
- `canonical_sources_locked` [ALL · roles=public] USING=`false` CHECK=`false`
- `canonical_sources_read` [SELECT · roles=public] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: canonical_sources_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
