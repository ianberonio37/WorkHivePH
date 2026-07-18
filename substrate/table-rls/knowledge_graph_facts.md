---
name: table-rls-knowledge_graph_facts
type: table-rls
source: db:pg_policies+pg_trigger:knowledge_graph_facts
source_sha: 6f4407bbb6f7e6c5
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `knowledge_graph_facts` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, subject_type*, subject_ref*, predicate*, object_type*, object_ref*, claim_text, payload*, confidence*, source_type*, source_ref, embedding, superseded_by, active*, created_by, created_at*, updated_at*

Policies:
- `kgf_delete_locked` [DELETE · roles=public] USING=`false` CHECK=`∅`
- `kgf_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `kgf_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`
- `kgf_update_locked` [UPDATE · roles=public] USING=`false` CHECK=`false`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
