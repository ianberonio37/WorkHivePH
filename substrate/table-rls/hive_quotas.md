---
name: table-rls-hive_quotas
type: table-rls
source: db:pg_policies+pg_trigger:hive_quotas
source_sha: 96dc5aacfe0d093c
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_quotas` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): hive_id*, max_rows_pm_comp, max_rows_community, max_rows_ai_reports, enforce_blocking*, created_at*, updated_at*, max_rows_logbook, max_rows_logbook_per_user, max_rows_inv_tx, max_storage_mb

Policies:
- `hive_quotas_write` [ALL · roles=public] USING=`false` CHECK=`false`
- `hive_quotas_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = hive_quotas.hive_id) AND (hm.` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
