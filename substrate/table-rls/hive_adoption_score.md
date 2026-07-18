---
name: table-rls-hive_adoption_score
type: table-rls
source: db:pg_policies+pg_trigger:hive_adoption_score
source_sha: 7a96fe99c8215b55
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_adoption_score` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, snapshot_date*, risk_score*, risk_tier*, active_ratio_risk*, momentum_risk*, supervisor_decay_risk*, stair_stall_risk*, new_worker_silence_risk*, top_reasons*, champion_candidate, champion_engagement, dropping_workers*, computed_at*, model_version*

Policies:
- `hive_adoption_score_delete_locked` [DELETE · roles=public] USING=`false` CHECK=`∅`
- `hive_adoption_score_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `hive_adoption_score_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`
- `hive_adoption_score_update_locked` [UPDATE · roles=public] USING=`false` CHECK=`false`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
