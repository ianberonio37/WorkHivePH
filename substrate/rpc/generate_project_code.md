---
name: rpc-generate_project_code
type: rpc
source: db:pg_proc:generate_project_code
source_sha: 936154c8293408e4
last_verified: 2026-07-13
supersedes: null
---
## rpc · `generate_project_code(p_hive_id uuid, p_type text, p_year text)` — SECURITY DEFINER, hive-scoped

Membership guard in body: **NO-GUARD** · EXECUTE: **authenticated-callable** (`=X/postgres,postgres=X/postgres,anon=X/postgres,authenticated=X/postgres,service`)

**FLAG:** DEFINER + hive arg + NO membership guard + authenticated-callable = CROSS-HIVE READ/LEAK suspect — live-verify.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
