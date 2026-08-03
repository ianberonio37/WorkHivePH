# Flywheel Turn #353

_2026-08-03T23:34:31_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 195 | 195 | · |
| L0    | total locked count      | 3274 | 3278 | ↑4 ❌ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## 🟡 Quarantined (2) — baseline deltas classified as noise, not scored (env up)

| Validator | Was | Now | Class | Note |
|---|---:|---:|---|---|
| `api_adoption` | 58 | 60 | **adoption-ratchet** |  |
| `edge_error_capture` | 58 | 60 | **adoption-ratchet** |  |

## ⏫ Promotions — queued for one-pass approval

- **9** rule candidate(s) (L-1→L0) · **1** sentinel candidate(s) (L0→L2)
- 12 tracked · 2 still below the recurrence gate
- top rule: `rule:python_tool:has_print_calls`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
