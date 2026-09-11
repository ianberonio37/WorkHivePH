---
name: table-rls-industry_standards_chunks
type: table-rls
source: db:pg_policies+pg_trigger:industry_standards_chunks
source_sha: 61c8d63bf036de56
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `industry_standards_chunks` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, standard_id*, chunk_num*, section, text*, embedding, source_pdf, created_at*

Policies:
- `isc_write_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `isc_read` [SELECT · roles=public] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: isc_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
