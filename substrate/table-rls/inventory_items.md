---
name: table-rls-inventory_items
type: table-rls
source: db:pg_policies+pg_trigger:inventory_items
source_sha: 14f7427637a9b62a
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `inventory_items` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, worker_name*, part_number*, part_name*, category, unit, qty_on_hand*, min_qty*, bin_location, notes, photo, updated_at, created_at, status, hive_id, submitted_by, approved_by, approved_at, auth_uid, linked_asset_node_ids

Policies:
- `inventory_items_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (((hive_id IS NULL) AND (auth_uid = auth.uid())) OR ((auth_uid = auth.uid()) AND (hive_id ` CHECK=`((auth.uid() IS NOT NULL) AND (((hive_id IS NULL) AND (auth_uid = auth.uid())) OR ((auth_uid = auth.uid()) AND (hive_id `
- `inventory_items_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`

Guard triggers: `tg_guard_approval`, `trg_bind_submitter_inventory_item`, `trg_daily_cap_inv_items`, `trg_text_caps_inv_items`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
