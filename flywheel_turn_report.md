# Flywheel Turn #503

_2026-11-05T14:11:10_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 229 | 229 | · |
| L0    | total locked count      | 3551 | 3550 | ↓1 ✅ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## ✅ Ratchets (1) — baselines tightened

| Validator | Was | Now |
|---|---:|---:|
| `event_listener_cleanup` | 5 | **4** |

## ⏫ Promotions — queued for one-pass approval

- **13** rule candidate(s) (L-1→L0) · **2** sentinel candidate(s) (L0→L2)
- 15 tracked · 0 still below the recurrence gate
- top rule: `rule:html:loads_utils_js`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
