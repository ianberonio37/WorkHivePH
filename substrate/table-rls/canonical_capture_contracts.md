---
name: table-rls-canonical_capture_contracts
type: table-rls
source: db:pg_policies+pg_trigger:canonical_capture_contracts
source_sha: d51c83651526b63d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `canonical_capture_contracts` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): capture_id*, surface*, source_page*, fields*, target_table*, target_columns*, validates_at*, contract_schema*, consumers*, notes, registered_at*

Policies:
- `canonical_capture_contracts_locked` [ALL · roles=public] USING=`false` CHECK=`false`
- `canonical_capture_contracts_read` [SELECT · roles=public] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: canonical_capture_contracts_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
