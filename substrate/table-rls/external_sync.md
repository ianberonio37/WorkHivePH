---
name: table-rls-external_sync
type: table-rls
source: db:pg_policies+pg_trigger:external_sync
source_sha: ad28987330c5fee9
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `external_sync` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, system_type*, external_id*, entity_type*, workhive_table, status, sync_payload, last_synced_at, sync_status, workhive_id

Policies:
- `external_sync_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
