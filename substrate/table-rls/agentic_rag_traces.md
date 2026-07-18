---
name: table-rls-agentic_rag_traces
type: table-rls
source: db:pg_policies+pg_trigger:agentic_rag_traces
source_sha: e888c1ebb992eb22
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `agentic_rag_traces` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, worker_name, question*, route*, stages*, retrievals*, retries*, grader_passed, checker_passed, citation_count, final_answer, total_tokens, latency_ms, user_rating, created_at*

Policies:
- `agentic_rag_traces_insert` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `agentic_rag_traces_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `agentic_rag_traces_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = age` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
