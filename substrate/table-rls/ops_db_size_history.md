---
name: table-rls-ops_db_size_history
type: table-rls
source: db:pg_policies+pg_trigger:ops_db_size_history
source_sha: 6d5d0d4182983ca6
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ops_db_size_history` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, captured_at*, db_bytes*, storage_bytes*, table_count*

Policies:
- `ops_db_size_history_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
