---
name: table-rls-ai_reports
type: table-rls
source: db:pg_policies+pg_trigger:ai_reports
source_sha: 8f80d4e8a3bc76d0
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ai_reports` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, report_type*, generated_at, report_json, summary, created_at

Policies:
- `ai_reports_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE ((hive_members.auth_uid ` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
