---
name: table-rls-ai_quality_log
type: table-rls
source: db:pg_policies+pg_trigger:ai_quality_log
source_sha: e28b356b737dbf1d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ai_quality_log` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, agent_id*, question_id*, question_text, expected_keywords, actual_answer, score, passed, judge_model, failure_reason, run_at*, run_id, outcome

Policies:
- `ai_quality_log_insert` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `ai_quality_log_read` [SELECT · roles=public] USING=`(( SELECT auth.uid() AS uid) IS NOT NULL)` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
