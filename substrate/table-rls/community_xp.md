---
name: table-rls-community_xp
type: table-rls
source: db:pg_policies+pg_trigger:community_xp
source_sha: d2cff75de8541854
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `community_xp` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): worker_name*, hive_id*, xp_total*, updated_at*, auth_uid

Policies:
- `community_xp_read` [SELECT · roles=public] USING=`(hive_id IN ( SELECT user_hive_ids() AS user_hive_ids))` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
