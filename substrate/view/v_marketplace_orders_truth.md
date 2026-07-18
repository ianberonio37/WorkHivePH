---
name: view-v_marketplace_orders_truth
type: view
source: db:pg_get_viewdef:v_marketplace_orders_truth
source_sha: 83d110bb28d2b331
last_verified: 2026-07-13
supersedes: null
---
## view · `v_marketplace_orders_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `marketplace_listings`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT o.id, o.listing_id, o.hive_id, o.buyer_name, o.seller_name, o.price, o.currency, o.status, o.escrow_release_at, o.buyer_confirmed_at, o.released_at, o.reviewed_at, o.created_at, o.updated_at, l.title AS listing_title, l.section AS listing_section, l.image_url AS listing_image_url, (o.status = 'pending_payment'::text) AS is_pending_payment, (o.status = 'escrow_hold'::text) AS is_escrow, (o.status = 'buyer_confirmed'::text) AS is_buyer_confirmed, (o.status = 'released'::text) AS is_released, (o.status = 'refunded'::text) AS is_refunded, (o.status = 'disputed'::text) AS is_disputed, (o.re …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
