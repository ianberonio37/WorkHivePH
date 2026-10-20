---
name: table-rls-best_practices
type: table-rls
source: db:pg_policies+pg_trigger:best_practices
source_sha: cc72ce34bcdb92ff
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `best_practices` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, created_at

Policies:
- `best_practices_public_read` [SELECT · roles=anon,authenticated] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: best_practices_public_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
