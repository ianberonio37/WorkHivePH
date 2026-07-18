---
name: view-v_wh_traces_slo
type: view
source: db:pg_get_viewdef:v_wh_traces_slo
source_sha: 8c8668643ea4ad10
last_verified: 2026-07-13
supersedes: null
---
## view · `v_wh_traces_slo`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `wh_traces`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT route, count(*) AS traced_total, count(*) FILTER (WHERE (((status >= 500) OR (error_code IS NOT NULL)) AND (COALESCE(status, 0) <> ALL (ARRAY[401, 403, 429])))) AS error_count, count(*) FILTER (WHERE (status = ANY (ARRAY[401, 403, 429]))) AS policy_rejections, count(*) FILTER (WHERE ((created_at >= (now() - '06:00:00'::interval)) AND ((status >= 500) OR (error_code IS NOT NULL)) AND (COALESCE(status, 0) <> ALL (ARRAY[401, 403, 429])))) AS errors_6h, count(*) FILTER (WHERE ((created_at >= (now() - '01:00:00'::interval)) AND ((status >= 500) OR (error_code IS NOT NULL)) AND (COALESCE(sta …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
