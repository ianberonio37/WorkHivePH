# Flywheel Turn #498

_2026-10-31T16:33:52_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 217 | 217 | · |
| L0    | total locked count      | 3557 | 3552 | ↓5 ✅ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## ✅ Ratchets (2) — baselines tightened

| Validator | Was | Now |
|---|---:|---:|
| `seeder_insert_columns` | 7 | **3** |
| `role_check` | 92 | **91** |

## ⏫ Promotions — queued for one-pass approval

- **13** rule candidate(s) (L-1→L0) · **2** sentinel candidate(s) (L0→L2)
- 15 tracked · 0 still below the recurrence gate
- top rule: `rule:html:loads_utils_js`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
