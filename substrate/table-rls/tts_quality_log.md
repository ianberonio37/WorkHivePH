---
name: table-rls-tts_quality_log
type: table-rls
source: db:pg_policies+pg_trigger:tts_quality_log
source_sha: 52d07a21c53ed7e8
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `tts_quality_log` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, worker_id, hive_id, persona, latency_ms, error_message, created_at

Policies:
- `tts_quality_log_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
