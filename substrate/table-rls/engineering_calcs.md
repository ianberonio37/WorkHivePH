---
name: table-rls-engineering_calcs
type: table-rls
source: db:pg_policies+pg_trigger:engineering_calcs
source_sha: fc4fb94256851a83
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `engineering_calcs` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id, worker_name, discipline, calc_type, project_name, inputs, results, narrative, created_at, bom_data, sow_text, auth_uid

Policies:
- `engineering_calcs_delete` [DELETE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))` CHECK=`∅`
- `engineering_calcs_insert` [INSERT · roles=public] USING=`∅` CHECK=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()) AND ((hive_id IS NULL) OR (hive_id IN ( SELECT hm.hive_id FROM hiv`
- `engineering_calcs_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((h` CHECK=`∅`
- `engineering_calcs_update` [UPDATE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))` CHECK=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()) AND ((hive_id IS NULL) OR (hive_id IN ( SELECT hm.hive_id FROM hiv`

Guard triggers: `trg_bind_submitter_engineering_calc`, `trg_daily_cap_eng_calcs`, `trg_text_caps_eng_calcs`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
