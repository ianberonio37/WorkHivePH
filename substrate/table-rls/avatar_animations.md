---
name: table-rls-avatar_animations
type: table-rls
source: db:pg_policies+pg_trigger:avatar_animations
source_sha: 1c3e61ed28851d2e
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `avatar_animations` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, duration_ms, config

Policies:
- `avatar_animations_public_read` [SELECT · roles=anon,authenticated] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: avatar_animations_public_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
