---
name: table-rls-canonical_agent_contracts
type: table-rls
source: db:pg_policies+pg_trigger:canonical_agent_contracts
source_sha: cac5c4777c7bcccf
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `canonical_agent_contracts` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): contract_id*, agent*, version*, json_schema*, consumers*, registered_at*

Policies:
- `canonical_agent_contracts_locked` [ALL · roles=public] USING=`false` CHECK=`false`
- `canonical_agent_contracts_read` [SELECT · roles=public] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: canonical_agent_contracts_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
