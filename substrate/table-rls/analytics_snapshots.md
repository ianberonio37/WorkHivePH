---
name: table-rls-analytics_snapshots
type: table-rls
source: db:pg_policies+pg_trigger:analytics_snapshots
source_sha: 85b924c2220b99a5
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `analytics_snapshots` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, phase*, period_days*, payload*, computed_at*, computed_by

Policies:
- `analytics_snapshots_member_read` [SELECT · roles=authenticated] USING=`(EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = analytics_snapshots.hive_id) AND (hm.auth_uid = auth.uid())` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
