---
name: table-rls-embedding_outbox
type: table-rls
source: db:pg_policies+pg_trigger:embedding_outbox
source_sha: 8ac1b9b1c150a233
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `embedding_outbox` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, source_table*, row_id*, hive_id, auth_uid, op*, enqueued_at*, attempts*, next_attempt_at*, claimed_at, done_at, last_error

Policies: (none)

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
