---
name: rpc-wh_retention_days
type: rpc
source: db:pg_proc:wh_retention_days
source_sha: 537e8686350dca3a
last_verified: 2026-07-13
supersedes: null
---
## rpc · `wh_retention_days(p_hive uuid)` — SECURITY DEFINER, hive-scoped

Membership guard in body: **NO-GUARD** · EXECUTE: **authenticated-callable** (`postgres=X/postgres,authenticated=X/postgres,service_role=X/postgres`)

**FLAG:** DEFINER + hive arg + NO membership guard + authenticated-callable = CROSS-HIVE READ/LEAK suspect — live-verify.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
