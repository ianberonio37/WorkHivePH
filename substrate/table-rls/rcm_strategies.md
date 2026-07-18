---
name: table-rls-rcm_strategies
type: table-rls
source: db:pg_policies+pg_trigger:rcm_strategies
source_sha: a13659c02d9a811d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `rcm_strategies` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, fmea_mode_id*, decision*, task_text, interval_days, rationale, weibull_fit_id, pf_interval_id, written_to_pm_scope_item_id, source*, ai_confidence, created_at*, updated_at*, approved_by, approved_at

Policies:
- `rcm_strategies_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND`
- `rcm_strategies_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`

Guard triggers: `tg_guard_approval`, `trg_text_caps_rcm_strat`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
