---
name: table-rls-ai_reply_feedback
type: table-rls
source: db:pg_policies+pg_trigger:ai_reply_feedback
source_sha: b55abe665ee883ff
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ai_reply_feedback` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id, auth_uid, worker_name, agent*, source*, page, persona, question*, answer, rating*, created_at*

Policies:
- `ai_reply_feedback_insert` [INSERT · roles=authenticated] USING=`∅` CHECK=`((auth_uid = auth.uid()) AND ((hive_id IS NULL) OR (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = ai_reply`
- `ai_reply_feedback_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `ai_reply_feedback_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND ((auth.uid() = auth_uid) OR ((hive_id IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_member` CHECK=`∅`

**Verdict:** FLAGS: client-writable TRUST/VALUE column(s) ['rating'] + no guard trigger — VALUE-INTEGRITY suspect (self-forgeable unless a BEFORE-trigger guards it or the display sources from a canonical table).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
