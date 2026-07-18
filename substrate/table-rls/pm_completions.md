---
name: table-rls-pm_completions
type: table-rls
source: db:pg_policies+pg_trigger:pm_completions
source_sha: 5c60df4ef56b9563
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `pm_completions` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, asset_id, scope_item_id, hive_id, worker_name*, status, notes, completed_at, auth_uid

Policies:
- `pm_completions_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()))` CHECK=`((auth.uid() IS NOT NULL) AND (auth_uid = auth.uid()) AND (((hive_id IS NULL) AND (EXISTS ( SELECT 1 FROM pm_assets pa W`
- `pm_completions_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((h` CHECK=`∅`

Guard triggers: `trg_bind_submitter_pm_completion`, `trg_daily_cap_pm_comp`, `trg_text_caps_pm_comp`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
