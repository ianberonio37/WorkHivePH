---
name: table-rls-equipment_reading_templates
type: table-rls
source: db:pg_policies+pg_trigger:equipment_reading_templates
source_sha: 2e6502e633db3379
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `equipment_reading_templates` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, category*, reading_key*, label*, unit*, placeholder*, sort_order, created_at

Policies:
- `equipment_reading_templates_public_read` [SELECT · roles=anon,authenticated] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: equipment_reading_templates_public_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
