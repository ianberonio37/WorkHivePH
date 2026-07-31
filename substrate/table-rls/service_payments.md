---
name: table-rls-service_payments
type: table-rls
source: db:pg_policies+pg_trigger:service_payments
source_sha: dc682e54cc740cf9
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `service_payments` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, request_id*, hive_id, amount_paid*, gcash_ref, method*, confirmed_by, paid_at*, created_at*

Policies:
- `service_payments_intake` [INSERT · roles=public] USING=`∅` CHECK=`((confirmed_by = auth.uid()) AND (EXISTS ( SELECT 1 FROM service_requests r WHERE ((r.id = service_payments.request_id) `
- `service_payments_read` [SELECT · roles=public] USING=`((confirmed_by = auth.uid()) OR is_marketplace_admin() OR (EXISTS ( SELECT 1 FROM service_requests r WHERE ((r.id = serv` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
