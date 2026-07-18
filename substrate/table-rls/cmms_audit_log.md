---
name: table-rls-cmms_audit_log
type: table-rls
source: db:pg_policies+pg_trigger:cmms_audit_log
source_sha: 9da3cbf16a95e6ba
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `cmms_audit_log` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, batch_id*, operation*, entity_type, system_type, rows_attempted, rows_written, rows_failed, quality_score, triggered_by, created_at

Policies:
- `cmms_audit_log_insert` [INSERT · roles=public] USING=`∅` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`
- `cmms_audit_log_select` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
