---
name: table-rls-service_outbox
type: table-rls
source: db:pg_policies+pg_trigger:service_outbox
source_sha: 7ee8a906752140a5
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `service_outbox` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, consumer*, payload*, status*, attempts*, max_attempts*, next_attempt_at*, request_id, last_error, created_at*, updated_at*

Policies: (none)

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
