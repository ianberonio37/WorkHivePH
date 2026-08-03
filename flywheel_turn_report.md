# Flywheel Turn #359

_2026-08-04T11:30:25_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 196 | 196 | · |
| L0    | total locked count      | 3474 | 3504 | ↑30 ❌ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## 🟡 Quarantined (1) — baseline deltas classified as noise, not scored (env up)

| Validator | Was | Now | Class | Note |
|---|---:|---:|---|---|
| `live_mcp_bank` | 192 | 222 | **adoption-ratchet** |  |

## ⏫ Promotions — queued for one-pass approval

- **12** rule candidate(s) (L-1→L0) · **1** sentinel candidate(s) (L0→L2)
- 14 tracked · 0 still below the recurrence gate
- top rule: `rule:python_tool:has_print_calls`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
