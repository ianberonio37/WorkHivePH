---
name: view-v_scheduled_call_health
type: view
source: db:pg_get_viewdef:v_scheduled_call_health
source_sha: caa928b41210ff2d
last_verified: 2026-07-13
supersedes: null
---
## view · `v_scheduled_call_health`

**security_invoker:** OFF ⚠  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `private`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT jobname, fn, called_at, status_code, error, settled_at FROM private.scheduled_calls c;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
