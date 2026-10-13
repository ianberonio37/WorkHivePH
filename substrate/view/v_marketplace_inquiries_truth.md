---
name: view-v_marketplace_inquiries_truth
type: view
source: db:pg_get_viewdef:v_marketplace_inquiries_truth
source_sha: ef86402d22f9921c
last_verified: 2026-07-13
supersedes: null
---
## view · `v_marketplace_inquiries_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `marketplace_listings`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT i.id, i.listing_id, i.hive_id, i.buyer_name, i.buyer_contact, i.seller_name, i.message, i.reply_text, i.replied_at, i.status, i.created_at, l.title AS listing_title, l.section AS listing_section, l.price AS listing_price, l.status AS listing_status, (i.status = 'pending'::text) AS is_pending, (i.status = 'replied'::text) AS is_replied, (i.status = 'closed'::text) AS is_closed, listing_is_mine(i.listing_id) AS to_me, inquiry_is_from_me(i.id) AS from_me FROM (marketplace_inquiries i LEFT JOIN marketplace_listings l ON ((l.id = i.listing_id)));

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
