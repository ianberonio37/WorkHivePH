---
name: table-rls-conversation_analytics
type: table-rls
source: db:pg_policies+pg_trigger:conversation_analytics
source_sha: 62d9ee7decc1a4fe
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `conversation_analytics` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, session_id, hive_id, question_category, answer_quality_rating, turn_num, user_feedback, model_confidence, response_time_ms, created_at

Policies:
- `conversation_analytics_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

**Verdict:** FLAGS: client-writable TRUST/VALUE column(s) ['answer_quality_rating'] + no guard trigger — VALUE-INTEGRITY suspect (self-forgeable unless a BEFORE-trigger guards it or the display sources from a canonical table).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
