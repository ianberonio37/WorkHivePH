---
name: table-rls-parts_staged_reservations
type: table-rls
source: db:pg_policies+pg_trigger:parts_staged_reservations
source_sha: c772204eb751ee6d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `parts_staged_reservations` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, asset_name*, item_id*, qty_reserved*, reserved_by, consumed_at, released_at, recommendation_id, notes

Policies:
- `parts_staged_reservations_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

Guard triggers: `trg_text_caps_parts_staged`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
