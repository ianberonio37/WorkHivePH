---
name: table-rls-push_subscriptions
type: table-rls
source: db:pg_policies+pg_trigger:push_subscriptions
source_sha: f71d91eabafe36fc
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `push_subscriptions` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: False · has auth_uid: True

Columns (*=NOT NULL): id*, auth_uid*, endpoint*, p256dh*, auth*, user_agent, created_at*, last_ok_at

Policies:
- `push_subscriptions_own` [ALL · roles=authenticated] USING=`(auth_uid = auth.uid())` CHECK=`(auth_uid = auth.uid())`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
