---
name: table-rls-platform_audit_log
type: table-rls
source: db:pg_policies+pg_trigger:platform_audit_log
source_sha: 0aff926fa1283687
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `platform_audit_log` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, actor_uid, actor*, action*, target_type, target_id, target_name, meta*, created_at*

Policies:
- `platform_audit_log_admin_read` [SELECT · roles=authenticated] USING=`( SELECT is_marketplace_admin() AS is_marketplace_admin)` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
