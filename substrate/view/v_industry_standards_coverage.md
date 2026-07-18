---
name: view-v_industry_standards_coverage
type: view
source: db:pg_get_viewdef:v_industry_standards_coverage
source_sha: 8ce8496a277134e3
last_verified: 2026-07-13
supersedes: null
---
## view · `v_industry_standards_coverage`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `industry_standards_chunks`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT s.id, s.standard_code, s.family, s.title, (count(isc.id))::integer AS chunk_count, (count(isc.id) FILTER (WHERE (isc.embedding IS NOT NULL)))::integer AS embedded_chunks, CASE WHEN (count(isc.id) = 0) THEN 'metadata_only'::text WHEN (count(isc.id) FILTER (WHERE (isc.embedding IS NOT NULL)) = count(isc.id)) THEN 'full_text_searchable'::text ELSE 'partially_embedded'::text END AS coverage_status FROM (industry_standards s LEFT JOIN industry_standards_chunks isc ON ((isc.standard_id = s.id))) GROUP BY s.id, s.standard_code, s.family, s.title;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
