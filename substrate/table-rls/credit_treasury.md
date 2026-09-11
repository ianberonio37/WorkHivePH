---
name: table-rls-credit_treasury
type: table-rls
source: db:pg_policies+pg_trigger:credit_treasury
source_sha: 4989eb96a6d133b4
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `credit_treasury` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, authorised_credits*, issued_credits*, created_at*, updated_at*

Policies:
- `credit_treasury_read` [SELECT · roles=authenticated] USING=`is_marketplace_admin()` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
