---
name: table-rls-canonical_capabilities
type: table-rls
source: db:pg_policies+pg_trigger:canonical_capabilities
source_sha: 185928a84cac941d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `canonical_capabilities` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): capability_id*, category*, primary_surface*, secondary_surfaces*, retired_surfaces*, description*, extension_pattern*, related_canonicals*, hive_isolation*, registered_at*

Policies:
- `canonical_capabilities_locked` [ALL · roles=public] USING=`false` CHECK=`false`
- `canonical_capabilities_read` [SELECT · roles=public] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: canonical_capabilities_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
