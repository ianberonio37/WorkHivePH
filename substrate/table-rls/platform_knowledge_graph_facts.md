---
name: table-rls-platform_knowledge_graph_facts
type: table-rls
source: db:pg_policies+pg_trigger:platform_knowledge_graph_facts
source_sha: ad531887967713fa
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `platform_knowledge_graph_facts` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, subject_type*, subject_ref*, predicate*, object_type*, object_ref*, claim_text, payload*, confidence*, source_type*, source_ref, embedding, superseded_by, active*, created_by, created_at*, updated_at*

Policies:
- `pkgf_write_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `pkgf_read` [SELECT · roles=public] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: pkgf_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
