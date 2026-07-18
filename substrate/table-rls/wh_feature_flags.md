---
name: table-rls-wh_feature_flags
type: table-rls
source: db:pg_policies+pg_trigger:wh_feature_flags
source_sha: bfb8fd8ee8f29772
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `wh_feature_flags` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): hive_id*, name*, enabled*, config, updated_at

Policies:
- `wh_feature_flags_hive_select` [SELECT · roles=authenticated] USING=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
