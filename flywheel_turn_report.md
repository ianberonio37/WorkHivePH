# Flywheel Turn #258

_2026-07-27T10:57:02_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 177 | 177 | · |
| L0    | total locked count      | 2488 | 2489 | ↑1 ❌ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## 🟡 Quarantined (1) — baseline deltas classified as noise, not scored (env up)

| Validator | Was | Now | Class | Note |
|---|---:|---:|---|---|
| `render_budget` | 9 | 10 | **adoption-ratchet** |  |

## ⏫ Promotions — queued for one-pass approval

- **7** rule candidate(s) (L-1→L0) · **1** sentinel candidate(s) (L0→L2)
- 9 tracked · 0 still below the recurrence gate
- top rule: `rule:python_tool:has_print_calls`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
