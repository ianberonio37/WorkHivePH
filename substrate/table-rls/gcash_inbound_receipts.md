---
name: table-rls-gcash_inbound_receipts
type: table-rls
source: db:pg_policies+pg_trigger:gcash_inbound_receipts
source_sha: 77284a6252968f99
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `gcash_inbound_receipts` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, reference*, amount*, sender_name, received_at, raw_text*, source*, matched_topup, match_state*, match_note, created_at*

Policies:
- `gcash_inbound_receipts_admin_read` [SELECT · roles=authenticated] USING=`is_platform_admin()` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
