---
name: table-rls-marketplace_sellers
type: table-rls
source: db:pg_policies+pg_trigger:marketplace_sellers
source_sha: 51cbf84860e116fc
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `marketplace_sellers` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, worker_name*, auth_uid, hive_id, tier*, kyb_verified*, kyb_verified_at, total_sales*, rating_avg, rating_count*, response_rate, response_time_h, created_at*, updated_at*, messenger_username, certifications, cert_verified*, cert_verified_at

Policies:
- `mkt_sellers_delete` [DELETE · roles=public] USING=`((auth_uid = auth.uid()) OR is_marketplace_admin())` CHECK=`∅`
- `mkt_sellers_insert` [INSERT · roles=public] USING=`∅` CHECK=`(auth_uid = auth.uid())`
- `marketplace_sellers_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `mkt_sellers_read` [SELECT · roles=public] USING=`(auth.uid() IS NOT NULL)` CHECK=`∅`
- `mkt_sellers_update` [UPDATE · roles=public] USING=`((auth_uid = auth.uid()) OR is_marketplace_admin())` CHECK=`((auth_uid = auth.uid()) OR is_marketplace_admin())`

Guard triggers: `trg_guard_seller_trust`, `trg_text_caps_mkt_sellers`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
