---
name: table-rls-skill_profiles
type: table-rls
source: db:pg_policies+pg_trigger:skill_profiles
source_sha: 69eaa0356fa815b4
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `skill_profiles` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): id*, worker_name*, primary_skill*, targets*, updated_at, auth_uid

Policies:
- `skill_profiles_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))` CHECK=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))`
- `skill_profiles_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))` CHECK=`∅`

Guard triggers: `trg_text_caps_skill_profiles`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
