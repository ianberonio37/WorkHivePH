---
name: view-v_marketplace_sellers_truth
type: view
source: db:pg_get_viewdef:v_marketplace_sellers_truth
source_sha: 2bc44f9d46fc36b1
last_verified: 2026-07-13
supersedes: null
---
## view · `v_marketplace_sellers_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `LATERAL`, `marketplace_listings`, `marketplace_orders`
**Trust/identity cols exposed:** `is_verified_public`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT s.id, s.worker_name, s.hive_id, s.tier, s.kyb_verified, s.kyb_verified_at, s.cert_verified, s.cert_verified_at, s.total_sales, s.rating_avg, s.rating_count, s.response_rate, s.response_time_h, s.messenger_username, s.certifications, s.created_at, s.updated_at, COALESCE(active_listings.n, (0)::bigint) AS active_listings_count, COALESCE(total_orders.n, (0)::bigint) AS total_orders_count, active_listings.last_at AS last_listed_at, total_orders.last_at AS last_order_at, (s.kyb_verified AND s.cert_verified) AS is_verified_public, ((s.messenger_username IS NOT NULL) AND (s.certifications IS  …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
