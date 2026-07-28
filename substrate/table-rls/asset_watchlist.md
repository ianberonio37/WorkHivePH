---
name: table-rls-asset_watchlist
type: table-rls
source: db:pg_policies+pg_trigger:asset_watchlist
source_sha: 517f16866b5a6526
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `asset_watchlist` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): hive_id*, worker_name*, asset_tag*, subscribed_at

Policies:
- `asset_watchlist_hive_all` [ALL · roles=authenticated] USING=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))` CHECK=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
