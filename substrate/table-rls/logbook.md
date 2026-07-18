---
name: table-rls-logbook
type: table-rls
source: db:pg_policies+pg_trigger:logbook
source_sha: da7e18b9339d2006
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `logbook` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, worker_name*, date*, machine, category, problem, action, knowledge, photo, status, created_at, maintenance_type, root_cause, downtime_hours, hive_id, parts_used, closed_at, tasklist_acknowledged, tasklist_note, pm_completion_id, failure_consequence, readings_json, production_output, auth_uid, wo_state, wo_assigned_to, updated_at*, asset_node_id, sync_meta*, loto_applied*, permit_reference

Policies:
- `logbook_delete` [DELETE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))` CHECK=`∅`
- `logbook_insert` [INSERT · roles=public] USING=`∅` CHECK=`((auth.uid() IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((h`
- `logbook_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((h` CHECK=`∅`
- `logbook_update` [UPDATE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))` CHECK=`∅`

Guard triggers: `tg_guard_approval`, `trg_bind_submitter_logbook`, `trg_logbook_text_caps`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
