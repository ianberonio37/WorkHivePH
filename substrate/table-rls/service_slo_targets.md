---
name: table-rls-service_slo_targets
type: table-rls
source: db:pg_policies+pg_trigger:service_slo_targets
source_sha: 22c86f52eb8abe81
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `service_slo_targets` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **False** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): sli*, target*, comparator*, unit*, window_days*, note, updated_at*

Policies: (none)

**Verdict:** FLAGS: RLS-DISABLED — world-open unless anon grants are revoked (audit has_table_privilege).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
