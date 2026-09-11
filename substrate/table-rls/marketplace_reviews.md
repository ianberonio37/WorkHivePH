---
name: table-rls-marketplace_reviews
type: table-rls
source: db:pg_policies+pg_trigger:marketplace_reviews
source_sha: 30cae21fd9991c3e
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `marketplace_reviews` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, listing_id, reviewer_name*, rating*, comment, verified_purchase*, created_at*, request_id, direction, reviewer_auth_uid

Policies:
- `mkt_reviews_delete` [DELETE · roles=public] USING=`((reviewer_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR is_marketplace_admin())` CHECK=`∅`
- `mkt_reviews_insert` [INSERT · roles=authenticated] USING=`∅` CHECK=`(is_marketplace_admin() OR ((reviewer_name IN ( SELECT auth_worker_names() AS auth_worker_names)) AND (verified_purchase`
- `service_review_intake` [INSERT · roles=authenticated] USING=`∅` CHECK=`(request_id IS NOT NULL)`
- `mkt_reviews_read` [SELECT · roles=public] USING=`true` CHECK=`∅`
- `mkt_reviews_update` [UPDATE · roles=public] USING=`((reviewer_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR is_marketplace_admin())` CHECK=`(is_marketplace_admin() OR ((reviewer_name IN ( SELECT auth_worker_names() AS auth_worker_names)) AND (verified_purchase`

Guard triggers: `trg_guard_service_review`, `trg_review_daily_cap`, `trg_text_caps_mkt_reviews`

**Verdict:** FLAGS: mkt_reviews_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
