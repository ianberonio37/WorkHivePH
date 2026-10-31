---
name: table-rls-external_sync
type: table-rls
source: db:pg_policies+pg_trigger:external_sync
source_sha: 0003daa96b4ed065
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `external_sync` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, system_type*, external_id*, entity_type*, workhive_table, status, sync_payload, last_synced_at, sync_status, workhive_id

Policies:
- `external_sync_supervisor_write` [ALL · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_supervisor_hive_ids() AS user_supervisor_hive_i` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_supervisor_hive_ids() AS user_supervisor_hive_i`
- `external_sync_member_read` [SELECT · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
