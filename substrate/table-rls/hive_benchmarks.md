---
name: table-rls-hive_benchmarks
type: table-rls
source: db:pg_policies+pg_trigger:hive_benchmarks
source_sha: c37324eb68c48dcd
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_benchmarks` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, equipment_category*, mtbf_days, mttr_hours, failure_count, sample_machines, period_days, computed_at

Policies:
- `hive_benchmarks_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
