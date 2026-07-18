---
name: rpc-get_hive_dashboard
type: rpc
source: db:pg_proc:get_hive_dashboard
source_sha: e6fe71e84a9ecd9c
last_verified: 2026-07-13
supersedes: null
---
## rpc · `get_hive_dashboard(p_hive_id uuid, p_day_start timestamp with time zone DEFAULT date_trunc('day'::text, now()))` — SECURITY DEFINER, hive-scoped

Membership guard in body: **GUARDED** · EXECUTE: **authenticated-callable** (`=X/postgres,postgres=X/postgres,anon=X/postgres,authenticated=X/postgres,service`)


Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
