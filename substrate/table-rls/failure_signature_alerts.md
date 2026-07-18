---
name: table-rls-failure_signature_alerts
type: table-rls
source: db:pg_policies+pg_trigger:failure_signature_alerts
source_sha: 2b0d28133f541e02
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `failure_signature_alerts` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, machine*, category, rule_id*, alert_title*, alert_detail, evidence, days_to_failure, severity, status, acknowledged_by, acknowledged_at, detected_at, expires_at

Policies:
- `failure_signature_alerts_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
