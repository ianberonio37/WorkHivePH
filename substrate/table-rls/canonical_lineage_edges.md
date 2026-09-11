---
name: table-rls-canonical_lineage_edges
type: table-rls
source: db:pg_policies+pg_trigger:canonical_lineage_edges
source_sha: d30b864df4705217
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `canonical_lineage_edges` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, source_kind*, source_id*, target_kind*, target_id*, notes, created_at*

Policies:
- `canonical_lineage_edges_read` [SELECT · roles=anon,authenticated] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: canonical_lineage_edges_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
