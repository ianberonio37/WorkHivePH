---
name: table-rls-network_benchmarks
type: table-rls
source: db:pg_policies+pg_trigger:network_benchmarks
source_sha: dc429d1734e53492
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `network_benchmarks` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **False** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, equipment_category*, industry*, avg_mtbf_days, p25_mtbf_days, p75_mtbf_days, sample_hives, period_days, computed_at

Policies: (none)

**Verdict:** FLAGS: RLS-DISABLED — world-open unless anon grants are revoked (audit has_table_privilege).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
