---
name: table-rls-marketplace_saved_searches
type: table-rls
source: db:pg_policies+pg_trigger:marketplace_saved_searches
source_sha: 661fc0bd9f41e891
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `marketplace_saved_searches` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, worker_name*, email, search_name*, section, category, query_text, price_min, price_max, last_sent_at, active*, created_at*

Policies:
- `mkt_saved_searches_owner_rw` [ALL · roles=public] USING=`(worker_name IN ( SELECT auth_worker_names() AS auth_worker_names))` CHECK=`(worker_name IN ( SELECT auth_worker_names() AS auth_worker_names))`

Guard triggers: `trg_text_caps_mkt_saved`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
