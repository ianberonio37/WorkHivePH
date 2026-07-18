# AU Adoption Report — Layer AU (FULLSTACK_COMPONENT_LIBRARY_ROADMAP §1)

> MEASURED 2026-07-17 over **32** family pages.

| ID | Canonical primitive | Adoption | % | Gap (first 8) |
|---|---|---|---|---|
| AU1 | restoreIdentityFromSession | **26/26** | **100%** | — |
| AU2 | session-settled reads (auth.getUser/getSession before RLS-gated queries) | **26/26** | **100%** | — |
| AU3 | login lockout RPCs | → `login fn (api-adoption) + mig 20260621000002` | — | — |
| AU4 | supervisor-reset-password flow | → `supervisor-reset-password fn (api-adoption + deploy runbook)` | — | — |
| AU5 | role floor: wh_hive_role hint + SERVER re-check | 15 page(s) | n/a | per-gate server-recheck heuristic queued (needs the role-gate map) |
