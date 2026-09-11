---
name: table-rls-voice_response_queue
type: table-rls
source: db:pg_policies+pg_trigger:voice_response_queue
source_sha: cca9602c57a5d3f9
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `voice_response_queue` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, worker_id*, session_id, transcript*, response, status, created_at, sent_at

Policies:
- `voice_queue_own_rows` [SELECT · roles=authenticated] USING=`(worker_id = auth.uid())` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
