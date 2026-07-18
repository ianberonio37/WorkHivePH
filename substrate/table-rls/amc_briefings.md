---
name: table-rls-amc_briefings
type: table-rls
source: db:pg_policies+pg_trigger:amc_briefings
source_sha: 98dccbcaa4774c09
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `amc_briefings` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, generated_at*, shift_date*, status*, brief*, model_version*, approved_by, approved_at, expires_at*, asset_count, pm_count, parts_count

Policies:
- `amc_briefings_delete_locked` [DELETE · roles=public] USING=`false` CHECK=`∅`
- `amc_briefings_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `amc_briefings_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`
- `amc_briefings_update_supervisor` [UPDATE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = amc_briefings.hive_id) AND (h` CHECK=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = amc_briefings.hive_id) AND (h`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
