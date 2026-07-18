---
name: table-rls-pdf_jobs
type: table-rls
source: db:pg_policies+pg_trigger:pdf_jobs
source_sha: 824277ac1e67fce3
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `pdf_jobs` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, uploaded_by, source_name*, source_url, target_table*, chunks_json, total_chunks, embedded_chunks*, status*, error_message, created_at*, started_at, finished_at

Policies:
- `pdf_jobs_insert` [INSERT · roles=public] USING=`∅` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = pdf`
- `pdf_jobs_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = pdf` CHECK=`∅`
- `pdf_jobs_update` [UPDATE · roles=public] USING=`false` CHECK=`∅`

Guard triggers: `trg_cap_pdf_job_size`, `trg_daily_cap_pdf_jobs`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
