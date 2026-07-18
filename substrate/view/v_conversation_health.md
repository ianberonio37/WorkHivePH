---
name: view-v_conversation_health
type: view
source: db:pg_get_viewdef:v_conversation_health
source_sha: b3d4aa663c86e008
last_verified: 2026-07-13
supersedes: null
---
## view · `v_conversation_health`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `conversation_analytics`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT question_category, count(*) AS total_questions, avg(answer_quality_rating) AS avg_quality, avg(response_time_ms) AS avg_latency_ms, ((count( CASE WHEN (answer_quality_rating = 1) THEN 1 ELSE NULL::integer END))::real / (count(*))::double precision) AS quality_ratio FROM conversation_analytics WHERE (created_at > (now() - '7 days'::interval)) GROUP BY question_category;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
