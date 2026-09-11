---
name: table-rls-service_voucher_redemptions
type: table-rls
source: db:pg_policies+pg_trigger:service_voucher_redemptions
source_sha: ed3f0c60150afaef
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `service_voucher_redemptions` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, voucher_id*, request_id*, consumer_auth_uid*, amount*, created_at*

Policies:
- `service_voucher_redemptions_own_read` [SELECT · roles=authenticated] USING=`((consumer_auth_uid = auth.uid()) OR is_marketplace_admin())` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
