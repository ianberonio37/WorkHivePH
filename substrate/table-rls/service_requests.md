---
name: table-rls-service_requests
type: table-rls
source: db:pg_policies+pg_trigger:service_requests
source_sha: bf48134580aa30fd
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `service_requests` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, client_auth_uid*, client_worker_name, hive_id, segment*, mode*, catalog_item_id, custom_scope, address, location, urgency*, budget, status*, matched_provider_id, broadcast_radius_m*, offer_ttl_expires_at, accepted_at, en_route_at, on_site_at, in_progress_at, completed_at, settled_at, cancelled_at, created_at*, updated_at*, broadcast_round*, pm_scope_item_id, showcase_consent*, showcase_post_id

Policies:
- `service_requests_client_insert` [INSERT · roles=authenticated] USING=`∅` CHECK=`(client_auth_uid = auth.uid())`
- `service_requests_party_read` [SELECT · roles=authenticated] USING=`((client_auth_uid = auth.uid()) OR ((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE` CHECK=`∅`
- `service_requests_party_update` [UPDATE · roles=authenticated] USING=`((client_auth_uid = auth.uid()) OR (matched_provider_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids` CHECK=`∅`

Guard triggers: `trg_daily_cap_service_requests`, `trg_guard_accept_requires_reservation`, `trg_guard_service_request_status`, `trg_guard_settle_requires_payment`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
