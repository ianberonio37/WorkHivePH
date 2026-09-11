---
name: table-rls-industry_standards
type: table-rls
source: db:pg_policies+pg_trigger:industry_standards
source_sha: 0cc3182ae67d21b5
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `industry_standards` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, standard_code*, family*, title*, current_version, effective_year, jurisdiction, last_verified_at*, planned_review_at, source_url, notes, created_at*, embedding

Policies:
- `std_write_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `std_read` [SELECT · roles=public] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: std_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
