# Flywheel Turn #107

_2026-06-14T11:35:51_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 46 | 46 | · |
| L0    | baselines tracked       | 98 | 100 | +2 ✅ |
| L0    | total locked count      | 355 | 346 | ↓9 ✅ |
| L2    | sentinel parity cases   | 35 | 35 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## ✅ Ratchets (1) — baselines tightened

| Validator | Was | Now |
|---|---:|---:|
| `clone_debt` | 70 | **61** |

## ⏫ Promotions — queued for one-pass approval

- **14** rule candidate(s) (L-1→L0) · **0** sentinel candidate(s) (L0→L2)
- 15 tracked · 1 still below the recurrence gate
- top rule: `rule:python_tool:has_print_calls`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
