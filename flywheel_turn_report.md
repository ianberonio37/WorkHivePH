# Flywheel Turn #295

_2026-07-28T17:57:01_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 185 | 186 | +1 ✅ |
| L0    | total locked count      | 2924 | 2945 | ↑21 ❌ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## 🟡 Quarantined (1) — baseline deltas classified as noise, not scored (env up)

| Validator | Was | Now | Class | Note |
|---|---:|---:|---|---|
| `render_budget` | 10 | 11 | **adoption-ratchet** |  |

## ⏫ Promotions — queued for one-pass approval

- **7** rule candidate(s) (L-1→L0) · **1** sentinel candidate(s) (L0→L2)
- 8 tracked · 0 still below the recurrence gate
- top rule: `rule:python_tool:has_print_calls`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
