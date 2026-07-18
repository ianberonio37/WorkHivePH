---
name: table-rls-unified_events
type: table-rls
source: db:pg_policies+pg_trigger:unified_events
source_sha: 10121b8a24d77948
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `unified_events` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, asset_tag, source*, source_id*, event_type*, occurred_at*, payload*, payload_text, embedding, hash*, ingested_at*

Policies:
- `ue_insert` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `ue_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = uni` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
