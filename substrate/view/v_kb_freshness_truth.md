---
name: view-v_kb_freshness_truth
type: view
source: db:pg_get_viewdef:v_kb_freshness_truth
source_sha: 76a4b3c47273cb56
last_verified: 2026-07-13
supersedes: null
---
## view · `v_kb_freshness_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `kb_chunks`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT doc_id, max(created_at) AS last_accessed, count(*) AS chunk_count, bool_and((embedding IS NOT NULL)) AS embedding_complete FROM kb_chunks GROUP BY doc_id;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
