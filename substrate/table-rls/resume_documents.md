---
name: table-rls-resume_documents
type: table-rls
source: db:pg_policies+pg_trigger:resume_documents
source_sha: b59056ce2e3252f7
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `resume_documents` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, auth_uid*, worker_name*, hive_id, title*, doc*, template*, updated_at*, created_at*

Policies:
- `resume_documents_delete` [DELETE · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid))` CHECK=`∅`
- `resume_documents_insert` [INSERT · roles=public] USING=`∅` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid) AND ((hive_id IS NULL) OR (hive_`
- `resume_documents_read` [SELECT · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid))` CHECK=`∅`
- `resume_documents_update` [UPDATE · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid))` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (( SELECT auth.uid() AS uid) = auth_uid) AND ((hive_id IS NULL) OR (hive_`

Guard triggers: `trg_daily_cap_resume_docs`, `trg_text_caps_resume_docs`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
