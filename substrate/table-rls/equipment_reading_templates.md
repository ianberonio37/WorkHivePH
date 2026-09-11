---
name: table-rls-equipment_reading_templates
type: table-rls
source: db:pg_policies+pg_trigger:equipment_reading_templates
source_sha: a445ef4d64b8ae5e
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `equipment_reading_templates` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **False** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, category*, reading_key*, label*, unit*, placeholder*, sort_order, created_at

Policies: (none)

**Verdict:** FLAGS: RLS-DISABLED — world-open unless anon grants are revoked (audit has_table_privilege).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
