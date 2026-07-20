---
name: table-rls-marketplace_orders
type: table-rls
source: db:pg_policies+pg_trigger:marketplace_orders
source_sha: 58b8ed2161957ae7
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `marketplace_orders` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, listing_id, hive_id, buyer_name*, seller_name*, price*, currency*, status*, escrow_release_at, buyer_confirmed_at, released_at, created_at*, updated_at*, reviewed_at

Policies:
- `mkt_orders_delete` [DELETE · roles=public] USING=`is_marketplace_admin()` CHECK=`∅`
- `mkt_orders_insert` [INSERT · roles=public] USING=`∅` CHECK=`(buyer_name IN ( SELECT auth_worker_names() AS auth_worker_names))`
- `marketplace_orders_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `mkt_orders_read` [SELECT · roles=public] USING=`((buyer_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR (seller_name IN ( SELECT auth_worker_names() AS a` CHECK=`∅`
- `mkt_orders_update` [UPDATE · roles=public] USING=`((buyer_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR (seller_name IN ( SELECT auth_worker_names() AS a` CHECK=`((buyer_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR (seller_name IN ( SELECT auth_worker_names() AS a`

Guard triggers: `trg_guard_marketplace_order_status`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
