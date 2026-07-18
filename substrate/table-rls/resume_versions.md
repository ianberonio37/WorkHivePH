---
name: table-rls-resume_versions
type: table-rls
source: db:pg_policies+pg_trigger:resume_versions
source_sha: afecb2ca04783975
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `resume_versions` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): id*, resume_id*, auth_uid*, doc*, note, created_at*

Policies:
- `resume_versions_delete` [DELETE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))` CHECK=`∅`
- `resume_versions_insert` [INSERT · roles=public] USING=`∅` CHECK=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))`
- `resume_versions_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))` CHECK=`∅`

Guard triggers: `trg_daily_cap_resume_versions`, `trg_text_caps_resume_versions`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
