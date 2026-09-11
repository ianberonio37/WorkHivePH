---
name: table-rls-service_catalog
type: table-rls
source: db:pg_policies+pg_trigger:service_catalog
source_sha: b5acfde193fcf9a1
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `service_catalog` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, segment*, category*, name*, description, unit*, base_rate*, active*, created_at*, updated_at*, requires_cert_level

Policies:
- `service_catalog_admin_write` [ALL · roles=authenticated] USING=`is_marketplace_admin()` CHECK=`is_marketplace_admin()`
- `service_catalog_read` [SELECT · roles=anon,authenticated] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: service_catalog_read (SELECT) USING is open ('true') — potential cross-tenant read/stream. client-writable TRUST/VALUE column(s) ['requires_cert_level'] + no guard trigger — VALUE-INTEGRITY suspect (self-forgeable unless a BEFORE-trigger guards it or the display sources from a canonical table).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
