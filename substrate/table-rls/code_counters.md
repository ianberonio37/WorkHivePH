---
name: table-rls-code_counters
type: table-rls
source: db:pg_policies+pg_trigger:code_counters
source_sha: 8795a7493d229d15
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `code_counters` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): scope*, last_seq*

Policies: (none)

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
