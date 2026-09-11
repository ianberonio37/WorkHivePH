---
name: table-rls-early_access_emails
type: table-rls
source: db:pg_policies+pg_trigger:early_access_emails
source_sha: 48c61ae019fcaffc
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `early_access_emails` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, email*, signed_up_at, source

Policies:
- `anon can insert early access email` [INSERT · roles=public] USING=`∅` CHECK=`true`
- `service role can read early access emails` [SELECT · roles=public] USING=`(auth.role() = 'service_role'::text)` CHECK=`∅`

Guard triggers: `trg_daily_cap_early_access`, `trg_text_caps_early_access`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
