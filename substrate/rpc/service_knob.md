---
name: rpc-service_knob
type: rpc
source: db:pg_proc:service_knob
source_sha: 98afda6d6dc9ce64
last_verified: 2026-07-13
supersedes: null
---
## rpc · `service_knob(p_hive uuid, p_key text)` — SECURITY DEFINER, hive-scoped

Membership guard in body: **NO-GUARD** · EXECUTE: **authenticated-callable** (`=X/postgres,postgres=X/postgres,anon=X/postgres,authenticated=X/postgres,service`)

**FLAG:** DEFINER + hive arg + NO membership guard + authenticated-callable = CROSS-HIVE READ/LEAK suspect — live-verify.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
