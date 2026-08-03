---
name: table-rls-hive_service_settings
type: table-rls
source: db:pg_policies+pg_trigger:hive_service_settings
source_sha: f769fa5ebada5639
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_service_settings` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): hive_id*, instant_ttl_seconds*, quote_ttl_seconds*, broadcast_radius_start_m*, broadcast_radius_max_m*, broadcast_widen_rounds*, tier_silver_sales*, tier_gold_sales*, updated_at*, created_at*, commission_pct*, listing_fee_pct*, cashback_pct*, min_list_balance*, reward_pct, reward_spend_cap_pct, holding_fee_pct, reward_max_per_listing, reward_min_per_listing, starter_grant, first_listings_before_sale*

Policies:
- `hive_service_settings_write` [ALL · roles=authenticated] USING=`(hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND (hm.status = 'active'::text) ` CHECK=`(hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND (hm.status = 'active'::text) `
- `hive_service_settings_read` [SELECT · roles=authenticated] USING=`(hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND (hm.status = 'active'::text))` CHECK=`∅`

**Verdict:** FLAGS: client-writable TRUST/VALUE column(s) ['tier_silver_sales', 'tier_gold_sales', 'min_list_balance'] + no guard trigger — VALUE-INTEGRITY suspect (self-forgeable unless a BEFORE-trigger guards it or the display sources from a canonical table).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
