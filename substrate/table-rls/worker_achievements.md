---
name: table-rls-worker_achievements
type: table-rls
source: db:pg_policies+pg_trigger:worker_achievements
source_sha: d4848c56457b77ff
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `worker_achievements` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): id*, auth_uid, worker_name*, achievement_id*, current_level*, xp_total*, last_action_at

Policies:
- `worker_achievements_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND ((auth_uid = auth.uid()) OR (worker_name IN ( SELECT user_hive_worker_names() AS user_hive` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
