---
name: table-rls-marketplace_watchlist
type: table-rls
source: db:pg_policies+pg_trigger:marketplace_watchlist
source_sha: 1fe383ede724d84c
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `marketplace_watchlist` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): id*, worker_name*, listing_id*, created_at*, auth_uid

Policies:
- `mkt_watchlist_owner_rw` [ALL · roles=public] USING=`(auth_uid = ( SELECT auth.uid() AS uid))` CHECK=`((auth_uid = ( SELECT auth.uid() AS uid)) AND (worker_name IN ( SELECT auth_worker_names() AS auth_worker_names)))`

Guard triggers: `trg_bind_watchlist_owner`, `trg_daily_cap_mkt_watchlist`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
