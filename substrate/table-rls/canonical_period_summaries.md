---
name: table-rls-canonical_period_summaries
type: table-rls
source: db:pg_policies+pg_trigger:canonical_period_summaries
source_sha: 294922784200a72a
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `canonical_period_summaries` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, asset_tag, level*, period_start*, period_end*, summary_text*, summary_json*, embedding, source_row_ids, standard_cites, generated_at*

Policies:
- `cps_insert` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `cps_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = can` CHECK=`∅`
- `cps_update` [UPDATE · roles=public] USING=`false` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
