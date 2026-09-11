---
name: table-rls-skill_exam_keys
type: table-rls
source: db:pg_policies+pg_trigger:skill_exam_keys
source_sha: 9350438ec847e222
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `skill_exam_keys` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): discipline*, level*, answer_key*

Policies: (none)

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
