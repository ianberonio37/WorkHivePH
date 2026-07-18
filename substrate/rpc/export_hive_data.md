---
name: rpc-export_hive_data
type: rpc
source: db:pg_proc:export_hive_data
source_sha: 2fb56f9439afd6c6
last_verified: 2026-07-13
supersedes: null
---
## rpc · `export_hive_data(p_hive_id uuid)` — SECURITY DEFINER, hive-scoped

Membership guard in body: **NO-GUARD** · EXECUTE: **service_role/postgres-only** (`postgres=X/postgres,service_role=X/postgres`)

**Note:** no in-body membership guard, but EXECUTE is service_role-only — exposure only if an edge fn invokes it with an unchecked hive_id (verify the caller).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
