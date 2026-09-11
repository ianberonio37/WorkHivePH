---
name: table-rls-achievement_xp_log
type: table-rls
source: db:pg_policies+pg_trigger:achievement_xp_log
source_sha: 5950a361e9a5f3e8
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `achievement_xp_log` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, worker_name*, achievement_id*, xp_earned*, source_action*, source_id, earned_at*, reversed_at

Policies:
- `ach_log_owner_read` [SELECT · roles=public] USING=`(worker_name IN ( SELECT auth_worker_names() AS auth_worker_names))` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
