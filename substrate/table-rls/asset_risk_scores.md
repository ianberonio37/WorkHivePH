---
name: table-rls-asset_risk_scores
type: table-rls
source: db:pg_policies+pg_trigger:asset_risk_scores
source_sha: 4a9633deb76439d5
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `asset_risk_scores` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, asset_name*, risk_score*, risk_level*, health_score, mtbf_days, days_until_failure, top_factors, components, model_version, generated_at

Policies:
- `asset_risk_scores_delete_locked` [DELETE · roles=public] USING=`false` CHECK=`∅`
- `asset_risk_scores_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `asset_risk_scores_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`
- `asset_risk_scores_update_locked` [UPDATE · roles=public] USING=`false` CHECK=`false`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
