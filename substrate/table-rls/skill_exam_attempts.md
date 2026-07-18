---
name: table-rls-skill_exam_attempts
type: table-rls
source: db:pg_policies+pg_trigger:skill_exam_attempts
source_sha: 23d088277ca1d8df
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `skill_exam_attempts` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): id*, worker_name*, discipline*, level*, score*, passed*, answers, attempted_at, auth_uid

Policies:
- `skill_exam_attempts_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))` CHECK=`∅`

Guard triggers: `trg_daily_cap_skill_exams`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
