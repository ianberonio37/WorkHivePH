---
name: view-v_community_reputation_truth
type: view
source: db:pg_get_viewdef:v_community_reputation_truth
source_sha: 3f112bdd54c8c443
last_verified: 2026-07-13
supersedes: null
---
## view · `v_community_reputation_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `community_posts`, `community_replies`, `community_xp`, `post_stats`, `reactions_recv`, `reply_stats`, `skill_badges`
**Trust/identity cols exposed:** `trust_tier`, `worker_name`, `xp_total`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  WITH participants AS ( SELECT DISTINCT community_posts.author_name AS worker_name, community_posts.hive_id FROM community_posts WHERE (community_posts.deleted_at IS NULL) UNION SELECT DISTINCT community_replies.author_name AS worker_name, community_replies.hive_id FROM community_replies UNION SELECT DISTINCT community_xp.worker_name, community_xp.hive_id FROM community_xp ), post_stats AS ( SELECT community_posts.author_name AS worker_name, community_posts.hive_id, count(*) AS total_posts, count(*) FILTER (WHERE community_posts.public) AS public_posts, count(*) FILTER (WHERE (community_posts. …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
