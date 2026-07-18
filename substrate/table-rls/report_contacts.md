---
name: table-rls-report_contacts
type: table-rls
source: db:pg_policies+pg_trigger:report_contacts
source_sha: be2c830997509313
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `report_contacts` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, name*, email, label, created_at

Policies:
- `report_contacts_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND`
- `report_contacts_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE ((hive_members.auth_uid ` CHECK=`∅`

Guard triggers: `trg_daily_cap_report_contacts`, `trg_text_caps_report_contacts`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
