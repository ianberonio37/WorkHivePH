---
name: table-rls-service_credit_topups
type: table-rls
source: db:pg_policies+pg_trigger:service_credit_topups
source_sha: 435f99c43f44b20b
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `service_credit_topups` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, account_type*, account_id*, payer_auth_uid*, amount*, gcash_ref*, status*, verified_by, verified_at, note, created_at*

Policies:
- `service_credit_topups_intake` [INSERT · roles=authenticated] USING=`∅` CHECK=`(payer_auth_uid = auth.uid())`
- `service_credit_topups_own` [SELECT · roles=authenticated] USING=`((payer_auth_uid = auth.uid()) OR is_marketplace_admin())` CHECK=`∅`
- `service_credit_topups_admin_update` [UPDATE · roles=authenticated] USING=`is_marketplace_admin()` CHECK=`∅`

Guard triggers: `trg_daily_cap_service_topups`, `trg_guard_service_topup_status`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
