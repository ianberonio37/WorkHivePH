# Flywheel Turn #355

_2026-08-04T04:04:39_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 195 | 195 | · |
| L0    | total locked count      | 3279 | 3283 | ↑4 ❌ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## 🟡 Quarantined (3) — baseline deltas classified as noise, not scored (env up)

| Validator | Was | Now | Class | Note |
|---|---:|---:|---|---|
| `db_adoption` | 181 | 182 | **adoption-ratchet** |  |
| `deploy_safety` | 2 | 3 | **adoption-ratchet** |  |
| `structured_log_adoption` | 42 | 44 | **adoption-ratchet** |  |

## ⏫ Promotions — queued for one-pass approval

- **10** rule candidate(s) (L-1→L0) · **1** sentinel candidate(s) (L0→L2)
- 15 tracked · 3 still below the recurrence gate
- top rule: `rule:python_tool:has_print_calls`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
