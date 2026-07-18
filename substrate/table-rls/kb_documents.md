---
name: table-rls-kb_documents
type: table-rls
source: db:pg_policies+pg_trigger:kb_documents
source_sha: a607632b063b7c15
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `kb_documents` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, title*, content_type, embedding_status, created_at, updated_at

Policies:
- `kb_documents_hive_access` [SELECT · roles=public] USING=`(EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = kb_documents.hive_id) AND (hm.auth_uid = auth.uid()) AND (h` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
