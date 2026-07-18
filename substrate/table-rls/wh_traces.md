---
name: table-rls-wh_traces
type: table-rls
source: db:pg_policies+pg_trigger:wh_traces
source_sha: 3619e62600318bcb
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `wh_traces` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): trace_id*, route*, hive_id, user_id, status, latency_ms, model_chain, error_code, created_at*

Policies:
- `wh_traces_grafana_slo_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `wh_traces_hive_read` [SELECT · roles=authenticated] USING=`(hive_id = ((current_setting('request.jwt.claims'::text, true))::json ->> 'hive_id'::text))` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
