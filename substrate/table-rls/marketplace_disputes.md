---
name: table-rls-marketplace_disputes
type: table-rls
source: db:pg_policies+pg_trigger:marketplace_disputes
source_sha: 193d5bf0354e81f4
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `marketplace_disputes` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, order_id, listing_id, opened_by*, seller_name*, reason*, evidence_urls, status*, seller_reply, seller_replied_at, admin_decision, admin_decided_at, resolved_at, created_at*, description, updated_at*, opened_by_auth_uid

Policies:
- `mkt_disp_delete` [DELETE · roles=public] USING=`is_marketplace_admin()` CHECK=`∅`
- `mkt_disp_insert` [INSERT · roles=authenticated] USING=`∅` CHECK=`((opened_by_auth_uid = ( SELECT auth.uid() AS uid)) AND (opened_by IN ( SELECT auth_worker_names() AS auth_worker_names)`
- `marketplace_disputes_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `mkt_disp_read` [SELECT · roles=public] USING=`((opened_by_auth_uid = ( SELECT auth.uid() AS uid)) OR listing_is_mine(listing_id) OR ((order_id IS NOT NULL) AND order_` CHECK=`∅`
- `mkt_disp_update` [UPDATE · roles=public] USING=`((opened_by_auth_uid = ( SELECT auth.uid() AS uid)) OR listing_is_mine(listing_id) OR ((order_id IS NOT NULL) AND order_` CHECK=`((opened_by_auth_uid = ( SELECT auth.uid() AS uid)) OR listing_is_mine(listing_id) OR ((order_id IS NOT NULL) AND order_`

Guard triggers: `trg_bind_dispute_opener`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
