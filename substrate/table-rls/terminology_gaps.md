---
name: table-rls-terminology_gaps
type: table-rls
source: db:pg_policies+pg_trigger:terminology_gaps
source_sha: 5d230c9209939fbd
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `terminology_gaps` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, language, domain, reported_by, created_at

Policies: (none)

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
