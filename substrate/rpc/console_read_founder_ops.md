---
name: rpc-console_read_founder_ops
type: rpc
source: db:pg_proc:console_read_founder_ops
source_sha: c9737fb899d18744
last_verified: 2026-07-13
supersedes: null
---
## rpc · `console_read_founder_ops(p_from timestamp with time zone DEFAULT (now() - '30 days'::interval), p_to timestamp with time zone)` — SECURITY DEFINER, hive-scoped

Membership guard in body: **NO-GUARD** · EXECUTE: **authenticated-callable** (`postgres=X/postgres,authenticated=X/postgres,service_role=X/postgres`)

**FLAG:** DEFINER + hive arg + NO membership guard + authenticated-callable = CROSS-HIVE READ/LEAK suspect — live-verify.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
