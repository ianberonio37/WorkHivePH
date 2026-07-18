---
name: table-rls-analytics_events
type: table-rls
source: db:pg_policies+pg_trigger:analytics_events
source_sha: a837812f627236ea
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `analytics_events` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, event_name*, page, props*, auth_uid, worker_name, hive_id, session_id, user_agent, created_at*

Policies:
- `analytics_events_insert_anyone` [INSERT · roles=anon,authenticated] USING=`∅` CHECK=`true`
- `analytics_events_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`
- `analytics_events_select_admin` [SELECT · roles=authenticated] USING=`(EXISTS ( SELECT 1 FROM (worker_profiles wp JOIN marketplace_platform_admins mpa ON ((mpa.worker_name = wp.display_name)` CHECK=`∅`

Guard triggers: `trg_bind_analytics_events_submitter`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
