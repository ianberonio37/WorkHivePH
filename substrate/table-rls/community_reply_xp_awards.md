---
name: table-rls-community_reply_xp_awards
type: table-rls
source: db:pg_policies+pg_trigger:community_reply_xp_awards
source_sha: 457eaa741c0f6fd5
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `community_reply_xp_awards` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): reply_id*, post_id*, author_name*, hive_id*, xp_awarded*, awarded_at*, reversed_at

Policies: (none)

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
