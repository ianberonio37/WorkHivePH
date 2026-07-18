---
name: table-rls-ai_cost_log
type: table-rls
source: db:pg_policies+pg_trigger:ai_cost_log
source_sha: 8e0ae99ca694ff7d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ai_cost_log` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, fn*, hive_id, worker_name, model*, provider, prompt_tokens, output_tokens, total_tokens, cost_usd, latency_ms, status*, created_at*, schema_compliance, user_feedback, prompt_hash, quality_rating

Policies:
- `ai_cost_log_insert` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `ai_cost_log_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `ai_cost_log_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = ai_` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
