---
name: view-v_storage_health
type: view
source: db:pg_get_viewdef:v_storage_health
source_sha: 6fe199d6e1626130
last_verified: 2026-07-13
supersedes: null
---
## view · `v_storage_health`

**security_invoker:** OFF ⚠  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `storage`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT bucket_id, count(*) AS objects, COALESCE(sum(((metadata ->> 'size'::text))::bigint), (0)::numeric) AS bytes, max(created_at) AS newest_at FROM storage.objects GROUP BY bucket_id;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
