# Flywheel Turn #254

_2026-07-24T19:23:26_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 175 | 176 | +1 ✅ |
| L0    | total locked count      | 2310 | 2411 | ↑101 ❌ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## 🟡 Quarantined (1) — baseline deltas classified as noise, not scored (env up)

| Validator | Was | Now | Class | Note |
|---|---:|---:|---|---|
| `clone_debt` | 55 | 56 | **adoption-ratchet** |  |

## ⏫ Promotions — queued for one-pass approval

- **6** rule candidate(s) (L-1→L0) · **1** sentinel candidate(s) (L0→L2)
- 7 tracked · 0 still below the recurrence gate
- top rule: `rule:python_tool:has_print_calls`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
