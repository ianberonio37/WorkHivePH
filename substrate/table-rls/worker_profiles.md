---
name: table-rls-worker_profiles
type: table-rls
source: db:pg_policies+pg_trigger:worker_profiles
source_sha: 6a1c57965bc61932
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `worker_profiles` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): id*, auth_uid*, username*, display_name*, email, created_at*, preferred_persona*, deactivated_at

Policies:
- `profiles insert own` [INSERT · roles=public] USING=`∅` CHECK=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))`
- `profiles_read_own` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))` CHECK=`∅`
- `profiles update own` [UPDATE · roles=public] USING=`(auth.uid() = auth_uid)` CHECK=`∅`

Guard triggers: `trg_text_caps_worker_profiles`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
