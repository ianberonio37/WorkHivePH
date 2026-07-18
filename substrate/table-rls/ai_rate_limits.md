---
name: table-rls-ai_rate_limits
type: table-rls
source: db:pg_policies+pg_trigger:ai_rate_limits
source_sha: 0e2de5660d660568
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ai_rate_limits` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): hive_id*, call_count*, window_start*, day_count*, day_window_start

Policies:
- `ai_rate_limits_locked` [ALL · roles=public] USING=`false` CHECK=`false`
- `ai_rate_limits_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
