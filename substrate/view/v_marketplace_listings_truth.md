---
name: view-v_marketplace_listings_truth
type: view
source: db:pg_get_viewdef:v_marketplace_listings_truth
source_sha: f8a8d04a2a55f518
last_verified: 2026-07-13
supersedes: null
---
## view · `v_marketplace_listings_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `marketplace_sellers`
**Trust/identity cols exposed:** `completed_sales`, `seller_kyb_verified`, `seller_rating_avg_live`, `seller_rating_count`, `seller_tier`, `seller_total_sales`, `seller_verified`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT l.id, l.hive_id, l.seller_name, l.seller_contact, (COALESCE(ms.kyb_verified, false) OR COALESCE(ms.cert_verified, false)) AS seller_verified, COALESCE(ms.total_sales, 0) AS completed_sales, ms.rating_avg, l.section, l.category, l.title, l.description, l.price, l.condition, l.location, l.image_url, l.status, l.view_count, l.created_at, l.updated_at, ms.tier AS seller_tier, ms.kyb_verified AS seller_kyb_verified, ms.total_sales AS seller_total_sales, ms.rating_avg AS seller_rating_avg_live, ms.rating_count AS seller_rating_count, ms.response_rate AS seller_response_rate, ms.response_time …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
