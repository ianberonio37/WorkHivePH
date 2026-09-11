---
name: table-rls-service_offers
type: table-rls
source: db:pg_policies+pg_trigger:service_offers
source_sha: 19d30b1f91b32b9e
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `service_offers` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, request_id*, provider_id*, kind*, price, eta_minutes, message, status*, created_at*, updated_at*

Policies:
- `service_offers_provider_insert` [INSERT · roles=authenticated] USING=`∅` CHECK=`(provider_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids))`
- `service_offers_party_read` [SELECT · roles=authenticated] USING=`((provider_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids)) OR (request_id IN ( SELECT r.id FROM se` CHECK=`∅`
- `service_offers_party_update` [UPDATE · roles=authenticated] USING=`((provider_id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids)) OR (request_id IN ( SELECT r.id FROM se` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
