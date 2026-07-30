---
name: table-rls-avatar_state
type: table-rls
source: db:pg_policies+pg_trigger:avatar_state
source_sha: 0fef9b7f25ba9608
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `avatar_state` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): id*, session_id, current_state, emotion, updated_at, auth_uid

Policies:
- `avatar_state_owner_rw` [ALL · roles=authenticated] USING=`(auth_uid = auth.uid())` CHECK=`(auth_uid = auth.uid())`
- `avatar_state_owner_read` [SELECT · roles=authenticated] USING=`(auth_uid = auth.uid())` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
