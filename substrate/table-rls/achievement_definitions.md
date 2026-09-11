---
name: table-rls-achievement_definitions
type: table-rls
source: db:pg_policies+pg_trigger:achievement_definitions
source_sha: 9b49493d852047e6
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `achievement_definitions` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, name*, description, icon, domain, pillar, max_level*, xp_per_level*

Policies:
- `ach_def_read` [SELECT · roles=public] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: ach_def_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
