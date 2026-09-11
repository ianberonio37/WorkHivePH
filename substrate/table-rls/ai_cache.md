---
name: table-rls-ai_cache
type: table-rls
source: db:pg_policies+pg_trigger:ai_cache
source_sha: 295c9d4c3b1818a6
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ai_cache` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): key*, model*, response_json*, tokens_in, tokens_out, hit_count*, created_at*, expires_at*

Policies:
- `ai_cache_service_all` [ALL · roles=service_role] USING=`true` CHECK=`true`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
