# Flywheel Turn #113

_2026-06-16T18:56:15_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 109 | 110 | +1 ✅ |
| L0    | total locked count      | 1277 | 1329 | ↑52 ❌ |
| L2    | sentinel parity cases   | 35 | 35 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## 🟡 Quarantined (1) — baseline deltas classified as noise, not scored (env up)

| Validator | Was | Now | Class | Note |
|---|---:|---:|---|---|
| `structured_log_adoption` | 1 | 8 | **adoption-ratchet** |  |

## ⏫ Promotions — queued for one-pass approval

- **15** rule candidate(s) (L-1→L0) · **1** sentinel candidate(s) (L0→L2)
- 16 tracked · 0 still below the recurrence gate
- top rule: `rule:python_tool:has_print_calls`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
