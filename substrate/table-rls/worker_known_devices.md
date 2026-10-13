---
name: table-rls-worker_known_devices
type: table-rls
source: db:pg_policies+pg_trigger:worker_known_devices
source_sha: b27abb227f7d5b4d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `worker_known_devices` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): auth_uid*, fp*, inputs*, first_seen_at*, last_seen_at*

Policies: (none)

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
