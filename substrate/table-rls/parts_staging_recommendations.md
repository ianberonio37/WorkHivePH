---
name: table-rls-parts_staging_recommendations
type: table-rls
source: db:pg_policies+pg_trigger:parts_staging_recommendations
source_sha: f115a27994f0e962
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `parts_staging_recommendations` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, asset_name*, risk_score*, failure_mode, parts*, rationale, confidence, status*, generated_at, expires_at, acted_at, acted_by, model_version

Policies:
- `parts_staging_recommendations_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
