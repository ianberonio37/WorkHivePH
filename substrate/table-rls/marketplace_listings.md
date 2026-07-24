---
name: table-rls-marketplace_listings
type: table-rls
source: db:pg_policies+pg_trigger:marketplace_listings
source_sha: f4a3fabab02f67e5
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `marketplace_listings` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, seller_name*, seller_contact, seller_verified*, completed_sales*, rating_avg, section*, category, title*, description, price, condition, location, image_url, status*, created_at*, updated_at*, search_vector, view_count*, part_number, source_inventory_item_id

Policies:
- `mkt_listings_delete` [DELETE · roles=public] USING=`((seller_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR is_marketplace_admin())` CHECK=`∅`
- `mkt_listings_insert` [INSERT · roles=public] USING=`∅` CHECK=`(seller_name IN ( SELECT auth_worker_names() AS auth_worker_names))`
- `marketplace_listings_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `mkt_listings_read` [SELECT · roles=public] USING=`((status = 'published'::text) OR (seller_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR is_marketplace_a` CHECK=`∅`
- `mkt_listings_update` [UPDATE · roles=public] USING=`((seller_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR is_marketplace_admin())` CHECK=`((seller_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR is_marketplace_admin())`

Guard triggers: `trg_guard_listing_status`, `trg_text_caps_mkt_listings`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
