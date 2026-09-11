---
name: table-rls-ops_artifact_metrics
type: table-rls
source: db:pg_policies+pg_trigger:ops_artifact_metrics
source_sha: 4d7e73de7d150425
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ops_artifact_metrics` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, artifact*, captured_at*, status, headline, metrics*

Policies:
- `ops_artifact_metrics_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
