---
name: table-rls-hive_readiness
type: table-rls
source: db:pg_policies+pg_trigger:hive_readiness
source_sha: d10f668c97674481
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_readiness` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, snapshot_date*, process_maturity_score*, data_quality_score*, infrastructure_resilience_score*, leadership_engagement_score*, cultural_adoption_score*, composite_score*, current_stair*, evidence*, blocker_summary, computed_at*, model_version*

Policies:
- `hive_readiness_write_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `hive_readiness_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `hive_readiness_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`
- `hive_readiness_update_locked` [UPDATE · roles=public] USING=`false` CHECK=`false`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
