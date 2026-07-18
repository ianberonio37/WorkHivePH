---
name: table-rls-pm_assets
type: table-rls
source: db:pg_policies+pg_trigger:pm_assets
source_sha: 783c12b19b06876b
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `pm_assets` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id, worker_name*, asset_name*, tag_id, location, category*, criticality, last_anchor_date, created_at, auth_uid, updated_at*

Policies:
- `pm_assets_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (((hive_id IS NULL) AND (auth_uid = auth.uid())) OR (hive_id IN ( SELECT hm.hive_id FROM h` CHECK=`((auth.uid() IS NOT NULL) AND (((hive_id IS NULL) AND (auth_uid = auth.uid())) OR (hive_id IN ( SELECT hm.hive_id FROM h`
- `pm_assets_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((h` CHECK=`∅`

Guard triggers: `trg_bind_submitter_pm_asset`, `trg_daily_cap_pm_assets`, `trg_text_caps_pm_assets`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
