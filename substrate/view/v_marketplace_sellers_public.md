---
name: view-v_marketplace_sellers_public
type: view
source: db:pg_get_viewdef:v_marketplace_sellers_public
source_sha: b27796ce08b0e17e
last_verified: 2026-07-13
supersedes: null
---
## view · `v_marketplace_sellers_public`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `marketplace_sellers_public_rows`
**Trust/identity cols exposed:** `rating_avg`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT worker_name, hive_id, tier, kyb_verified, cert_verified, total_sales, (rating_avg)::numeric(3,2) AS rating_avg, rating_count, (response_rate)::numeric(5,2) AS response_rate, (response_time_h)::numeric(6,1) AS response_time_h, active_listings_count, total_orders_count, last_listed_at, last_order_at, is_verified_public, profile_complete, messenger_username, certifications, kyb_verified_at, cert_verified_at, created_at FROM marketplace_sellers_public_rows() r(worker_name, hive_id, tier, kyb_verified, cert_verified, total_sales, rating_avg, rating_count, response_rate, response_time_h, act …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
