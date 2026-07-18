---
name: rpc-get_seller_community_reputation
type: rpc
source: db:pg_proc:get_seller_community_reputation
source_sha: 7e4cff72ff3e2c0d
last_verified: 2026-07-13
supersedes: null
---
## rpc · `get_seller_community_reputation(p_worker_name text, p_hive_id uuid)` — SECURITY DEFINER, hive-scoped

Membership guard in body: **NO-GUARD** · EXECUTE: **authenticated-callable** (`postgres=X/postgres,authenticated=X/postgres,service_role=X/postgres`)

**FLAG:** DEFINER + hive arg + NO membership guard + authenticated-callable = CROSS-HIVE READ/LEAK suspect — live-verify.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
