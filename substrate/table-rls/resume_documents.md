---
name: table-rls-resume_documents
type: table-rls
source: db:pg_policies+pg_trigger:resume_documents
source_sha: 5cdeea2bee3d2980
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `resume_documents` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, auth_uid*, worker_name*, hive_id, title*, doc*, template*, updated_at*, created_at*

Policies:
- `resume_documents_delete` [DELETE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))` CHECK=`∅`
- `resume_documents_insert` [INSERT · roles=public] USING=`∅` CHECK=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))`
- `resume_documents_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))` CHECK=`∅`
- `resume_documents_update` [UPDATE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))` CHECK=`((auth.uid() IS NOT NULL) AND (auth.uid() = auth_uid))`

Guard triggers: `trg_daily_cap_resume_docs`, `trg_text_caps_resume_docs`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
