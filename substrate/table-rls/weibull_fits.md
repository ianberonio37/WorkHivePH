---
name: table-rls-weibull_fits
type: table-rls
source: db:pg_policies+pg_trigger:weibull_fits
source_sha: a122aec1a9537529
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `weibull_fits` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, asset_id*, fmea_mode_id, beta, eta_days, failure_pattern, n_failures*, n_censored*, fit_method*, log_likelihood, source_window_days*, generated_at*

Policies:
- `weibull_fits_write` [ALL · roles=public] USING=`false` CHECK=`false`
- `weibull_fits_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
