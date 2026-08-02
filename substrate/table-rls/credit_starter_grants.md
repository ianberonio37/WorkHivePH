---
name: table-rls-credit_starter_grants
type: table-rls
source: db:pg_policies+pg_trigger:credit_starter_grants
source_sha: 71cf1a78a6c10c5b
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `credit_starter_grants` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): auth_uid*, amount*, granted_at*

Policies: (none)

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
