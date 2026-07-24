---
name: table-rls-asset_nodes
type: table-rls
source: db:pg_policies+pg_trigger:asset_nodes
source_sha: 698db827d51cad8e
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `asset_nodes` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id, auth_uid, worker_name, parent_id, level*, tag*, name*, iso_class, criticality*, location, manufacturer, model, serial_no, install_date, external_ids*, legacy_asset_id, pm_asset_id, status*, submitted_by, approved_by, approved_at, created_at*, updated_at*, lifecycle*, ideal_cycle_time_seconds, rejection_reason

Policies:
- `asset_nodes_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (((auth_uid = auth.uid()) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE (` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND`
- `asset_nodes_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`

Guard triggers: `tg_guard_approval`, `trg_bind_submitter_asset_nodes`, `trg_daily_cap_asset_nodes`, `trg_text_caps_asset_nodes`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
