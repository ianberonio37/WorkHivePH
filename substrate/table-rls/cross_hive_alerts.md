---
name: table-rls-cross_hive_alerts
type: table-rls
source: db:pg_policies+pg_trigger:cross_hive_alerts
source_sha: 5d337df63df504db
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `cross_hive_alerts` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **False** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, alert_reason, severity, detected_at

Policies: (none)

**Verdict:** FLAGS: RLS-DISABLED — world-open unless anon grants are revoked (audit has_table_privilege).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
