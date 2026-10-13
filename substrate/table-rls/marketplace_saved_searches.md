---
name: table-rls-marketplace_saved_searches
type: table-rls
source: db:pg_policies+pg_trigger:marketplace_saved_searches
source_sha: c507422c28731c85
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `marketplace_saved_searches` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): id*, worker_name*, email, search_name*, section, category, query_text, price_min, price_max, last_sent_at, active*, created_at*, auth_uid

Policies:
- `mkt_saved_searches_owner_rw` [ALL · roles=public] USING=`(auth_uid = auth.uid())` CHECK=`((auth_uid = auth.uid()) AND (worker_name IN ( SELECT auth_worker_names() AS auth_worker_names)))`

Guard triggers: `trg_bind_saved_search_owner`, `trg_text_caps_mkt_saved`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
