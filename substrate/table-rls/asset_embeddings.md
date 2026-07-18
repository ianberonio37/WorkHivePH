---
name: table-rls-asset_embeddings
type: table-rls
source: db:pg_policies+pg_trigger:asset_embeddings
source_sha: d2ec12a730ed3e5d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `asset_embeddings` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): node_id*, hive_id*, summary, embedding, refreshed_at*

Policies:
- `asset_embeddings_write` [ALL · roles=public] USING=`false` CHECK=`false`
- `asset_embeddings_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
