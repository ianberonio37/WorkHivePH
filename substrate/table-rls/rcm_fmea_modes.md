---
name: table-rls-rcm_fmea_modes
type: table-rls
source: db:pg_policies+pg_trigger:rcm_fmea_modes
source_sha: d6d8bac216336074
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `rcm_fmea_modes` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, asset_id*, function_text*, failure_mode*, effect_text, cause_text, severity, occurrence, detection, rpn, consequence_class, source*, ai_confidence, notes, created_at*, updated_at*, created_by, approved_by, approved_at

Policies:
- `rcm_fmea_modes_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND`
- `rcm_fmea_modes_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`

Guard triggers: `tg_guard_approval`, `trg_text_caps_rcm_fmea`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
