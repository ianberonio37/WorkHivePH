---
name: rpc-get_oee_by_machine
type: rpc
source: db:pg_proc:get_oee_by_machine
source_sha: 0b1535081956ed3e
last_verified: 2026-07-13
supersedes: null
---
## rpc · `get_oee_by_machine(p_hive_id uuid, p_period_days integer DEFAULT 90)` — SECURITY DEFINER, hive-scoped

Membership guard in body: **NO-GUARD** · EXECUTE: **service_role/postgres-only** (`postgres=X/postgres,service_role=X/postgres`)

**Note:** no in-body membership guard, but EXECUTE is service_role-only — exposure only if an edge fn invokes it with an unchecked hive_id (verify the caller).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
