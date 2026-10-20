---
name: table-rls-network_benchmarks
type: table-rls
source: db:pg_policies+pg_trigger:network_benchmarks
source_sha: 540e0a4892502ed0
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `network_benchmarks` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, equipment_category*, industry*, avg_mtbf_days, p25_mtbf_days, p75_mtbf_days, sample_hives, period_days, computed_at

Policies:
- `network_benchmarks_public_read` [SELECT · roles=anon,authenticated] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: network_benchmarks_public_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
