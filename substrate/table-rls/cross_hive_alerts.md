---
name: table-rls-cross_hive_alerts
type: table-rls
source: db:pg_policies+pg_trigger:cross_hive_alerts
source_sha: 51299f1ccd08942d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `cross_hive_alerts` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, alert_reason, severity, detected_at

Policies:
- `cross_hive_alerts_public_read` [SELECT · roles=anon,authenticated] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: cross_hive_alerts_public_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
