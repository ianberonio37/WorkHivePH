---
name: table-rls-offline_snapshot_cache
type: table-rls
source: db:pg_policies+pg_trigger:offline_snapshot_cache
source_sha: 59d7ee7fe0308ae9
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `offline_snapshot_cache` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, worker_id*, hive_id*, snapshot_data*, snapshot_hash, expires_at

Policies:
- `offline_snapshot_cache_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
