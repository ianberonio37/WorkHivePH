# Flywheel Turn #386

_2026-08-20T20:38:53_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 200 | 201 | +1 ✅ |
| L0    | total locked count      | 3289 | 3286 | ↓3 ✅ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## ✅ Ratchets (2) — baselines tightened

| Validator | Was | Now |
|---|---:|---:|
| `design_tokens` | 168 | **166** |
| `unbounded_query` | 1 | **0** |

## ⏫ Promotions — queued for one-pass approval

- **12** rule candidate(s) (L-1→L0) · **1** sentinel candidate(s) (L0→L2)
- 13 tracked · 0 still below the recurrence gate
- top rule: `rule:python_tool:has_print_calls`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
