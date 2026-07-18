---
name: table-rls-project_links
type: table-rls
source: db:pg_policies+pg_trigger:project_links
source_sha: e1606e77a604898d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `project_links` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, project_id*, hive_id*, link_type*, link_id, label, meta*, created_at*

Policies:
- `project_links_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

Guard triggers: `trg_daily_cap_project_links`, `trg_text_caps_project_links`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
