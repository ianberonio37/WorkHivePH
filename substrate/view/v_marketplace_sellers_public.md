---
name: view-v_marketplace_sellers_public
type: view
source: db:pg_get_viewdef:v_marketplace_sellers_public
source_sha: 904dd89db8819932
last_verified: 2026-07-13
supersedes: null
---
## view · `v_marketplace_sellers_public`

**security_invoker:** OFF ⚠  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `LATERAL`, `marketplace_listings`, `marketplace_orders`
**Trust/identity cols exposed:** `cert_verified_at`, `certifications`, `is_verified_public`, `kyb_verified_at`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT s.worker_name, s.hive_id, s.tier, s.kyb_verified, s.cert_verified, s.total_sales, s.rating_avg, s.rating_count, s.response_rate, s.response_time_h, COALESCE(active_listings.n, (0)::bigint) AS active_listings_count, COALESCE(total_orders.n, (0)::bigint) AS total_orders_count, active_listings.last_at AS last_listed_at, total_orders.last_at AS last_order_at, (s.kyb_verified AND s.cert_verified) AS is_verified_public, ((s.messenger_username IS NOT NULL) AND (s.certifications IS NOT NULL)) AS profile_complete, CASE WHEN (auth.uid() IS NOT NULL) THEN s.messenger_username ELSE NULL::text END  …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
