---
name: table-rls-cmms_audit_log
type: table-rls
source: db:pg_policies+pg_trigger:cmms_audit_log
source_sha: d16a39039a9120b7
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `cmms_audit_log` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, batch_id*, operation*, entity_type, system_type, rows_attempted, rows_written, rows_failed, quality_score, triggered_by, created_at

Policies:
- `cmms_audit_log_insert` [INSERT · roles=public] USING=`∅` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`
- `cmms_audit_log_select` [SELECT · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`∅`
- `cmms_audit_log_mark_rolled_back` [UPDATE · roles=authenticated] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)) AND (operation = ` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)) AND (operation = `

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
