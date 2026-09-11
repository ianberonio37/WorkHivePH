---
name: table-rls-fallback_model_faq
type: table-rls
source: db:pg_policies+pg_trigger:fallback_model_faq
source_sha: 5610f947354498a7
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `fallback_model_faq` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, answer*, category

Policies:
- `fallback_faq_read` [SELECT · roles=public] USING=`(auth.role() = 'authenticated'::text)` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
