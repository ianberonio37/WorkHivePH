---
name: table-rls-alert_dismissals
type: table-rls
source: db:pg_policies+pg_trigger:alert_dismissals
source_sha: 14e5d12146be0ff0
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `alert_dismissals` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, alert_key*, action*, actor, snooze_until, created_at*

Policies:
- `alert_dismissals_member_delete` [DELETE · roles=authenticated] USING=`(EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = alert_dismissals.hive_id) AND (hm.auth_uid = auth.uid()) AN` CHECK=`∅`
- `alert_dismissals_member_write` [INSERT · roles=authenticated] USING=`∅` CHECK=`(EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = alert_dismissals.hive_id) AND (hm.auth_uid = auth.uid()) AN`
- `alert_dismissals_member_read` [SELECT · roles=authenticated] USING=`(EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = alert_dismissals.hive_id) AND (hm.auth_uid = auth.uid()) AN` CHECK=`∅`
- `alert_dismissals_member_update` [UPDATE · roles=authenticated] USING=`(EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = alert_dismissals.hive_id) AND (hm.auth_uid = auth.uid()) AN` CHECK=`(EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = alert_dismissals.hive_id) AND (hm.auth_uid = auth.uid()) AN`

Guard triggers: `trg_daily_cap_alert_dismissals`, `trg_text_caps_alert_dismissals`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
