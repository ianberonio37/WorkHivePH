---
name: table-rls-hive_audit_log
type: table-rls
source: db:pg_policies+pg_trigger:hive_audit_log
source_sha: c772be33e6e9b23e
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_audit_log` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, actor*, action*, target_type, target_id, target_name, meta, created_at*

Policies:
- `hive_audit_log_insert_member` [INSERT · roles=public] USING=`∅` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`
- `hive_audit_log_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `hive_audit_log_select_supervisor` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_supervisor_hive_ids() AS user_supervisor_hive_ids)))` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
