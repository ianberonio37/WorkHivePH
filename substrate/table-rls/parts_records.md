---
name: table-rls-parts_records
type: table-rls
source: db:pg_policies+pg_trigger:parts_records
source_sha: 8bfc060cdabb3f2a
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `parts_records` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, worker_name*, job_ref, job_type, date, duration, parts, created_at, hive_id, asset_ref_id

Policies:
- `parts_records_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

Guard triggers: `trg_bind_submitter_parts_record`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
