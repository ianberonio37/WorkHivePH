---
name: table-rls-pm_scope_items
type: table-rls
source: db:pg_policies+pg_trigger:pm_scope_items
source_sha: f10ade3a270faca3
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `pm_scope_items` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, asset_id, hive_id, item_text*, frequency*, anchor_date, is_custom, created_at

Policies:
- `pm_scope_items_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM pm_assets pa WHERE ((pa.id = pm_scope_items.asset_id) AND (((pa.hi` CHECK=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM pm_assets pa WHERE ((pa.id = pm_scope_items.asset_id) AND (NOT (pa`
- `pm_scope_items_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (asset_id IN ( SELECT pa.id FROM (pm_assets pa JOIN hive_members hm ON ((pa.hive_id = hm.h` CHECK=`∅`

Guard triggers: `trg_daily_cap_pm_scope`, `trg_text_caps_pm_scope`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
