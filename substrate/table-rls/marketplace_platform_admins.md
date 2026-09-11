---
name: table-rls-marketplace_platform_admins
type: table-rls
source: db:pg_policies+pg_trigger:marketplace_platform_admins
source_sha: 3aecb2452ba460b7
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `marketplace_platform_admins` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): worker_name*, granted_at*, granted_by*

Policies:
- `mkt_admins_write` [ALL · roles=public] USING=`is_marketplace_admin()` CHECK=`is_marketplace_admin()`
- `mkt_admins_read_self` [SELECT · roles=public] USING=`(worker_name IN ( SELECT wp.display_name FROM worker_profiles wp WHERE (wp.auth_uid = auth.uid())))` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
