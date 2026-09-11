---
name: table-rls-canonical_standards
type: table-rls
source: db:pg_policies+pg_trigger:canonical_standards
source_sha: 441698f80aa26770
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `canonical_standards` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): standard_id*, body*, number*, version*, discipline*, title*, contract*, url, registered_at*

Policies:
- `canonical_standards_locked` [ALL · roles=public] USING=`false` CHECK=`false`
- `canonical_standards_read` [SELECT · roles=public] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: canonical_standards_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
