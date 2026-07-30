---
name: view-v_service_area_presence
type: view
source: db:pg_get_viewdef:v_service_area_presence
source_sha: 305f0275c46109f5
last_verified: 2026-07-13
supersedes: null
---
## view · `v_service_area_presence`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `LATERAL`
**Trust/identity cols exposed:** `verified_online`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT a.area AS service_area, (count(DISTINCT sp.id))::integer AS providers_online, array_agg(DISTINCT c.cat ORDER BY c.cat) AS categories, (count(DISTINCT sp.id) FILTER (WHERE sp.verified))::integer AS verified_online, 1 AS _source_count, max(sp.updated_at) AS _freshness_ts, 'service_area_presence:v2'::text AS _canonical_version FROM ((service_providers sp CROSS JOIN LATERAL unnest(sp.service_areas) a(area)) CROSS JOIN LATERAL unnest(sp.categories) c(cat)) WHERE ((sp.availability = 'online'::text) AND (COALESCE(a.area, ''::text) <> ''::text)) GROUP BY a.area;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
