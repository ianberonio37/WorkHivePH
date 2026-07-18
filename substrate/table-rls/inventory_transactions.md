---
name: table-rls-inventory_transactions
type: table-rls
source: db:pg_policies+pg_trigger:inventory_transactions
source_sha: 40e7678c62b16a36
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `inventory_transactions` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, worker_name*, item_id*, type*, qty_change*, qty_after*, note, job_ref, created_at, hive_id, auth_uid

Policies:
- `inventory_transactions_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM inventory_items ii WHERE ((ii.id = inventory_transactions.item_id)` CHECK=`((auth.uid() IS NOT NULL) AND ((auth_uid = auth.uid()) OR (auth_uid IS NULL)) AND (EXISTS ( SELECT 1 FROM inventory_item`
- `inventory_transactions_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((h` CHECK=`∅`

Guard triggers: `trg_daily_cap_inv_tx`, `trg_text_caps_inv_tx`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
