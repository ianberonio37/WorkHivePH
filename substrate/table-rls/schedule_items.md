---
name: table-rls-schedule_items
type: table-rls
source: db:pg_policies+pg_trigger:schedule_items
source_sha: 12c75d3b8da21be2
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `schedule_items` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): id*, worker_name*, title, date, start_time, end_time, category, notes, logbook_ref, item_status, created_at, auth_uid, source_kind, source_ref

Policies:
- `schedule_items_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))` CHECK=`∅`
- `schedule_items_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))` CHECK=`∅`

Guard triggers: `trg_daily_cap_schedule_items`, `trg_text_caps_schedule_items`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
