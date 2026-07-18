---
name: table-rls-ai_user_rate_limits
type: table-rls
source: db:pg_policies+pg_trigger:ai_user_rate_limits
source_sha: fb98aaf064b1dee3
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ai_user_rate_limits` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): user_id*, hive_id, call_count*, window_start*, day_count*, day_window_start

Policies:
- `ai_user_rate_limits_own` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (user_id = (auth.uid())::text))` CHECK=`((auth.uid() IS NOT NULL) AND (user_id = (auth.uid())::text))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
