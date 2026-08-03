---
name: table-rls-credit_reservations
type: table-rls
source: db:pg_policies+pg_trigger:credit_reservations
source_sha: bc15dc4b13aececc
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `credit_reservations` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, listing_id, seller_name, hive_id, amount*, state*, released_at, created_at*, request_id

Policies:
- `credit_reservations_read` [SELECT · roles=public] USING=`((seller_name IN ( SELECT auth_worker_names() AS auth_worker_names)) OR is_marketplace_admin())` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
