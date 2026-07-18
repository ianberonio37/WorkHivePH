---
name: rpc-increment_community_xp
type: rpc
source: db:pg_proc:increment_community_xp
source_sha: 2c82a100cf3d375c
last_verified: 2026-07-13
supersedes: null
---
## rpc · `increment_community_xp(p_worker_name text, p_hive_id uuid, p_amount integer)` — SECURITY DEFINER, hive-scoped

Membership guard in body: **NO-GUARD** · EXECUTE: **service_role/postgres-only** (`postgres=X/postgres,service_role=X/postgres`)

**Note:** no in-body membership guard, but EXECUTE is service_role-only — exposure only if an edge fn invokes it with an unchecked hive_id (verify the caller).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
