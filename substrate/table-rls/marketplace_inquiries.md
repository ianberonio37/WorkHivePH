---
name: table-rls-marketplace_inquiries
type: table-rls
source: db:pg_policies+pg_trigger:marketplace_inquiries
source_sha: 8580e0338cf7e98a
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `marketplace_inquiries` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, listing_id, hive_id, buyer_name*, buyer_contact, message*, status*, created_at*, seller_name, reply_text, replied_at

Policies:
- `mkt_inq_delete` [DELETE · roles=public] USING=`is_marketplace_admin()` CHECK=`∅`
- `mkt_inq_insert` [INSERT · roles=public] USING=`∅` CHECK=`(buyer_name IN ( SELECT auth_worker_names() AS auth_worker_names))`
- `mkt_inq_read` [SELECT · roles=public] USING=`((buyer_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR (seller_name IN ( SELECT auth_worker_names() AS a` CHECK=`∅`
- `mkt_inq_update` [UPDATE · roles=public] USING=`((buyer_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR (seller_name IN ( SELECT auth_worker_names() AS a` CHECK=`((buyer_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR (seller_name IN ( SELECT auth_worker_names() AS a`

Guard triggers: `trg_text_caps_mkt_inquiries`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
