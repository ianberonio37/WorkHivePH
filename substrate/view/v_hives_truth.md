---
name: view-v_hives_truth
type: view
source: db:pg_get_viewdef:v_hives_truth
source_sha: 03c6b6b28365dffc
last_verified: 2026-07-13
supersedes: null
---
## view · `v_hives_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `asset_nodes`, `hive_members`, `hives`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id, name, invite_code, created_by, created_at, intent, preferred_persona, ( SELECT (count(*))::integer AS count FROM hive_members hm WHERE ((hm.hive_id = h.id) AND (hm.status = 'active'::text))) AS member_count, ( SELECT (count(*))::integer AS count FROM asset_nodes an WHERE ((an.hive_id = h.id) AND (an.status = 'approved'::text))) AS asset_count, ( SELECT min(hm.joined_at) AS min FROM hive_members hm WHERE ((hm.hive_id = h.id) AND (hm.status = 'active'::text))) AS first_member_joined_at, (intent = '{}'::jsonb) AS intent_not_captured FROM hives h;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
