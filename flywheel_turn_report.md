# Flywheel Turn #354

_2026-08-04T01:00:48_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 195 | 195 | · |
| L0    | total locked count      | 3278 | 3279 | ↑1 ❌ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## ✅ Ratchets (1) — baselines tightened

| Validator | Was | Now |
|---|---:|---:|
| `guard_mutation` | 100 | **99** |

## 🟡 Quarantined (1) — baseline deltas classified as noise, not scored (env up)

| Validator | Was | Now | Class | Note |
|---|---:|---:|---|---|
| `envelope_return_shape` | 3 | 5 | **adoption-ratchet** |  |

## ⏫ Promotions — queued for one-pass approval

- **11** rule candidate(s) (L-1→L0) · **1** sentinel candidate(s) (L0→L2)
- 12 tracked · 0 still below the recurrence gate
- top rule: `rule:python_tool:has_print_calls`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
