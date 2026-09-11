---
name: table-rls-marketplace_watchlist
type: table-rls
source: db:pg_policies+pg_trigger:marketplace_watchlist
source_sha: 1bd2b824fdd87804
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `marketplace_watchlist` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, worker_name*, listing_id*, created_at*

Policies:
- `mkt_watchlist_owner_rw` [ALL · roles=public] USING=`(worker_name IN ( SELECT auth_worker_names() AS auth_worker_names))` CHECK=`(worker_name IN ( SELECT auth_worker_names() AS auth_worker_names))`

Guard triggers: `trg_daily_cap_mkt_watchlist`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
