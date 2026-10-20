---
name: table-rls-ph_intelligence_reports
type: table-rls
source: db:pg_policies+pg_trigger:ph_intelligence_reports
source_sha: be636ddedfb06cab
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ph_intelligence_reports` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, period*, period_type, hive_count, wo_count, equipment_count, report_json, narrative, generated_at

Policies:
- `ph_intelligence_reports_public_read` [SELECT · roles=anon,authenticated] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: ph_intelligence_reports_public_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
