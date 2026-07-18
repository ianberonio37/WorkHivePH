---
name: table-rls-project_change_orders
type: table-rls
source: db:pg_policies+pg_trigger:project_change_orders
source_sha: 9670a0c24b01393d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `project_change_orders` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, project_id*, hive_id*, co_number*, title*, scope_change*, reason, cost_impact_php, schedule_impact_days, status*, requested_by*, requested_at*, approved_by, approved_at, rejection_reason, created_at*

Policies:
- `project_change_orders_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

Guard triggers: `tg_guard_approval_project_co`, `trg_daily_cap_project_co`, `trg_text_caps_project_co`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
