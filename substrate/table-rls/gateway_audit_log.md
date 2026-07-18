---
name: table-rls-gateway_audit_log
type: table-rls
source: db:pg_policies+pg_trigger:gateway_audit_log
source_sha: 6891ebcb4915aede
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `gateway_audit_log` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id, worker_name, auth_uid, route*, request_id, method*, status_code, latency_ms, ip_hash, ua_fingerprint, error_class, created_at*

Policies:
- `gateway_audit_insert` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `gateway_audit_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = gat` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
