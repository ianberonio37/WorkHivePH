---
name: table-rls-language_preferences
type: table-rls
source: db:pg_policies+pg_trigger:language_preferences
source_sha: 51fd95de496762ae
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `language_preferences` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): worker_id*, updated_at

Policies:
- `language_prefs_owner_rw` [ALL · roles=authenticated] USING=`(worker_id IN ( SELECT worker_profiles.id FROM worker_profiles WHERE (worker_profiles.auth_uid = auth.uid())))` CHECK=`(worker_id IN ( SELECT worker_profiles.id FROM worker_profiles WHERE (worker_profiles.auth_uid = auth.uid())))`
- `language_prefs_owner_read` [SELECT · roles=authenticated] USING=`(worker_id IN ( SELECT worker_profiles.id FROM worker_profiles WHERE (worker_profiles.auth_uid = auth.uid())))` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
