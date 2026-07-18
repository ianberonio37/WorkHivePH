---
name: table-rls-skill_badges
type: table-rls
source: db:pg_policies+pg_trigger:skill_badges
source_sha: 5d56f3dbeffc46f5
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `skill_badges` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): id*, worker_name*, discipline*, level*, earned_at, exam_score*, auth_uid, badge_key

Policies:
- `skill_badges_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))` CHECK=`∅`

Guard triggers: `trg_daily_cap_skill_badges`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
