---
name: rpc-update_dialog_state
type: rpc
source: db:pg_proc:update_dialog_state
source_sha: 968bbda0251863e9
last_verified: 2026-07-13
supersedes: null
---
## rpc · `update_dialog_state(p_hive_id uuid, p_session_id text, p_turn_num integer, p_intent text, p_confidence real, p_context_s)` — SECURITY DEFINER, hive-scoped

Membership guard in body: **NO-GUARD** · EXECUTE: **authenticated-callable** (`=X/postgres,postgres=X/postgres,anon=X/postgres,authenticated=X/postgres,service`)

**FLAG:** DEFINER + hive arg + NO membership guard + authenticated-callable = CROSS-HIVE READ/LEAK suspect — live-verify.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
