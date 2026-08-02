---
name: rpc-listing_reservation_amount
type: rpc
source: db:pg_proc:listing_reservation_amount
source_sha: f75bfbe938db2f72
last_verified: 2026-07-13
supersedes: null
---
## rpc · `listing_reservation_amount(p_hive uuid, p_price numeric)` — SECURITY DEFINER, hive-scoped

Membership guard in body: **NO-GUARD** · EXECUTE: **authenticated-callable** (`=X/postgres,postgres=X/postgres,anon=X/postgres,authenticated=X/postgres,service`)

**FLAG:** DEFINER + hive arg + NO membership guard + authenticated-callable = CROSS-HIVE READ/LEAK suspect — live-verify.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
