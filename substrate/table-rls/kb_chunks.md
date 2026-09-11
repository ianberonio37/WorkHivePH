---
name: table-rls-kb_chunks
type: table-rls
source: db:pg_policies+pg_trigger:kb_chunks
source_sha: d77cc87d794ab46a
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `kb_chunks` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, doc_id*, chunk_num, text*, embedding, created_at

Policies:
- `kb_chunks_hive_access` [SELECT · roles=public] USING=`(EXISTS ( SELECT 1 FROM (kb_documents kd JOIN hive_members hm ON ((hm.hive_id = kd.hive_id))) WHERE ((kd.id = kb_chunks.` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
