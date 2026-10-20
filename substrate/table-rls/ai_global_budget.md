---
name: table-rls-ai_global_budget
type: table-rls
source: db:pg_policies+pg_trigger:ai_global_budget
source_sha: 0a14af6f28d2ebf7
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ai_global_budget` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, minute_count*, minute_window_start, day_count*, day_window_start, shed_count_today*, deny_count_today*, updated_at*, depth_samples_today*, depth_sum_today*, max_depth_today*

Policies: (none)

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
