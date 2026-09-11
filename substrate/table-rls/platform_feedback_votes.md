---
name: table-rls-platform_feedback_votes
type: table-rls
source: db:pg_policies+pg_trigger:platform_feedback_votes
source_sha: b4ef44fa6080c9ca
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `platform_feedback_votes` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): feedback_id*, voter_token*

Policies:
- `anon vote delete` [DELETE · roles=public] USING=`true` CHECK=`∅`
- `anon vote insert` [INSERT · roles=public] USING=`∅` CHECK=`true`
- `anon vote read` [SELECT · roles=public] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: anon vote read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
