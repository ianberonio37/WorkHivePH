---
name: table-rls-canonical_formulas
type: table-rls
source: db:pg_policies+pg_trigger:canonical_formulas
source_sha: 0ce505a660895bbd
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `canonical_formulas` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): formula_id*, name*, domain*, standard_ids*, library_source*, inputs*, outputs*, formula_text*, description*, registered_at*

Policies:
- `canonical_formulas_locked` [ALL · roles=public] USING=`false` CHECK=`false`
- `canonical_formulas_read` [SELECT · roles=public] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: canonical_formulas_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
