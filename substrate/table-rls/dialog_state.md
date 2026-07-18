---
name: table-rls-dialog_state
type: table-rls
source: db:pg_policies+pg_trigger:dialog_state
source_sha: 2b4f072ac0da67ca
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `dialog_state` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, worker_id*, session_id*, current_intent, intent_confidence, context_slots, clarification_pending, clarification_prompt, last_turn_num, created_at, updated_at

Policies:
- `dialog_state_insert_own` [INSERT · roles=public] USING=`∅` CHECK=`(auth.uid() = worker_id)`
- `dialog_state_worker_access` [SELECT · roles=public] USING=`(auth.uid() = worker_id)` CHECK=`∅`
- `dialog_state_update_own` [UPDATE · roles=public] USING=`(auth.uid() = worker_id)` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
