---
name: table-rls-agent_memory
type: table-rls
source: db:pg_policies+pg_trigger:agent_memory
source_sha: 2dc04fe3f1324130
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `agent_memory` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id, worker_name*, auth_uid, agent_id*, kind*, turn_text, summary, meta, created_at*, session_id, turn_num, user_input, user_input_hash, assistant_response, intent_classification, intent_confidence, embedding, response_time_ms, expires_at, worker_id

Policies:
- `agent_memory_delete` [DELETE · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid))` CHECK=`∅`
- `agent_memory_insert` [INSERT · roles=public] USING=`∅` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid))`
- `agent_memory_insert_own` [INSERT · roles=public] USING=`∅` CHECK=`((( SELECT auth.uid() AS uid) = worker_id) OR (( SELECT auth.uid() AS uid) = auth_uid))`
- `agent_memory_read` [SELECT · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND ((( SELECT auth.uid() AS uid) = auth_uid) OR (( SELECT auth.uid() AS uid)` CHECK=`∅`
- `agent_memory_worker_access` [SELECT · roles=public] USING=`((( SELECT auth.uid() AS uid) = worker_id) OR (( SELECT auth.uid() AS uid) = auth_uid))` CHECK=`∅`
- `agent_memory_update` [UPDATE · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid))` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
