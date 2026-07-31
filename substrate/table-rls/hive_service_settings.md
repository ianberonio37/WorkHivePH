---
name: table-rls-hive_service_settings
type: table-rls
source: db:pg_policies+pg_trigger:hive_service_settings
source_sha: 9d7f9949f7ee5a47
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_service_settings` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): hive_id*, instant_ttl_seconds*, quote_ttl_seconds*, broadcast_radius_start_m*, broadcast_radius_max_m*, broadcast_widen_rounds*, tier_silver_sales*, tier_gold_sales*, updated_at*, created_at*

Policies:
- `hive_service_settings_write` [ALL · roles=authenticated] USING=`(hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND (hm.status = 'active'::text) ` CHECK=`(hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND (hm.status = 'active'::text) `
- `hive_service_settings_read` [SELECT · roles=authenticated] USING=`(hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND (hm.status = 'active'::text))` CHECK=`∅`

**Verdict:** FLAGS: client-writable TRUST/VALUE column(s) ['tier_silver_sales', 'tier_gold_sales'] + no guard trigger — VALUE-INTEGRITY suspect (self-forgeable unless a BEFORE-trigger guards it or the display sources from a canonical table).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
