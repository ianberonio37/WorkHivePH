---
name: table-rls-service_vouchers
type: table-rls
source: db:pg_policies+pg_trigger:service_vouchers
source_sha: 1775db061f525d88
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `service_vouchers` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, code*, kind*, value*, segment, max_uses, per_user_limit*, expires_at, active*, created_at*

Policies:
- `service_vouchers_admin_write` [ALL · roles=authenticated] USING=`is_marketplace_admin()` CHECK=`is_marketplace_admin()`
- `service_vouchers_read` [SELECT · roles=authenticated] USING=`((active = true) OR is_marketplace_admin())` CHECK=`∅`

Guard triggers: `trg_guard_vouchers_retired`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
