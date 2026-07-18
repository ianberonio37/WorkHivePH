---
name: view-v_community_posts_truth
type: view
source: db:pg_get_viewdef:v_community_posts_truth
source_sha: f28c489ff68b484c
last_verified: 2026-07-13
supersedes: null
---
## view · `v_community_posts_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `hives`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT p.id, p.hive_id, p.author_name, p.auth_uid, p.content, p.category, p.pinned, p.flagged, p.public, p.created_at, p.edited_at, p.mentions, p.deleted_at, h.name AS hive_name, (p.deleted_at IS NOT NULL) AS is_deleted, (p.edited_at IS NOT NULL) AS is_edited, p.updated_at FROM (community_posts p LEFT JOIN hives h ON ((h.id = p.hive_id)));

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
