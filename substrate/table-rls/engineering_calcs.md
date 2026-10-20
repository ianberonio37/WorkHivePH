---
name: table-rls-engineering_calcs
type: table-rls
source: db:pg_policies+pg_trigger:engineering_calcs
source_sha: 7c071f1a5083bc6f
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `engineering_calcs` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id, worker_name, discipline, calc_type, project_name, inputs, results, narrative, created_at, bom_data, sow_text, auth_uid

Policies:
- `engineering_calcs_delete` [DELETE · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid)))` CHECK=`∅`
- `engineering_calcs_insert` [INSERT · roles=public] USING=`∅` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid)) AND ((hive_id IS NULL) OR (hive_`
- `engineering_calcs_read` [SELECT · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_mem` CHECK=`∅`
- `engineering_calcs_update` [UPDATE · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid)))` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (auth_uid = ( SELECT auth.uid() AS uid)) AND ((hive_id IS NULL) OR (hive_`

Guard triggers: `trg_bind_submitter_engineering_calc`, `trg_daily_cap_eng_calcs`, `trg_text_caps_eng_calcs`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
