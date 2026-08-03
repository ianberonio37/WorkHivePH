---
name: view-v_credit_posture
type: view
source: db:pg_get_viewdef:v_credit_posture
source_sha: cdf5213b3e856eb5
last_verified: 2026-07-13
supersedes: null
---
## view · `v_credit_posture`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `credit_treasury`, `pg_namespace`, `pg_proc`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT ( SELECT (count(*) = 0) FROM (pg_proc p JOIN pg_namespace n ON ((n.oid = p.pronamespace))) WHERE ((n.nspname = 'public'::name) AND (p.proname ~* '(withdraw|cash_?out|redeem_for_cash|payout_credits)'::text))) AS no_cash_out_function, ( SELECT (count(*) > 0) FROM (pg_trigger t JOIN pg_proc p ON ((p.oid = t.tgfoid))) WHERE ((p.proname = 'guard_credits_non_transferable'::name) AND (NOT t.tgisinternal))) AS transfer_guard_live, ( SELECT credit_treasury.authorised_credits FROM credit_treasury WHERE (credit_treasury.id = 1)) AS authorised_credits, ( SELECT credit_treasury.issued_credits FROM  …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
