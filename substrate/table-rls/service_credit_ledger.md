---
name: table-rls-service_credit_ledger
type: table-rls
source: db:pg_policies+pg_trigger:service_credit_ledger
source_sha: 9725a32508f6e28f
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `service_credit_ledger` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, account_type*, account_id*, entry_type*, amount*, ref_kind, ref_id, note, created_at*

Policies:
- `service_credit_ledger_own_read` [SELECT · roles=authenticated] USING=`(((account_type = 'consumer'::text) AND (account_id = auth.uid())) OR ((account_type = 'provider'::text) AND (account_id` CHECK=`∅`

Guard triggers: `trg_guard_voucher_within_budget`, `trg_reward_spend_cap`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
