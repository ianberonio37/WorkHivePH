---
name: table-rls-login_attempts
type: table-rls
source: db:pg_policies+pg_trigger:login_attempts
source_sha: 78602f675d267373
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `login_attempts` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): identifier*, ip*, fail_count*, window_start*, locked_until, updated_at*

Policies:
- `login_attempts_grafana_read` [SELECT · roles=grafana_reader] USING=`true` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
