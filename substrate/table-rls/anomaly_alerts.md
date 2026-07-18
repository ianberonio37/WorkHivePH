---
name: table-rls-anomaly_alerts
type: table-rls
source: db:pg_policies+pg_trigger:anomaly_alerts
source_sha: c86f2be61b1ba012
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `anomaly_alerts` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, asset_id, alert_type, severity, metric_name, metric_value, metric_threshold, deviation_percent, description, action_suggested, detected_at, suppressed_until, acknowledged_at, created_at

Policies:
- `anomaly_alerts_hive_access` [SELECT · roles=public] USING=`(EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = anomaly_alerts.hive_id) AND (hm.auth_uid = auth.uid()) AND ` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
