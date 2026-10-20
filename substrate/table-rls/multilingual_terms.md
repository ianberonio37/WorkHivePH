---
name: table-rls-multilingual_terms
type: table-rls
source: db:pg_policies+pg_trigger:multilingual_terms
source_sha: 9cd7221d29118f9d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `multilingual_terms` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, domain*, english_term*, tagalog_term, visayan_term, context, created_at

Policies:
- `multilingual_terms_public_read` [SELECT · roles=anon,authenticated] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: multilingual_terms_public_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
