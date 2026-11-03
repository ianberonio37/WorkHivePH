# Flywheel Turn #501

_2026-11-03T21:20:34_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 226 | 226 | · |
| L0    | total locked count      | 3552 | 3546 | ↓6 ✅ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## ✅ Ratchets (3) — baselines tightened

| Validator | Was | Now |
|---|---:|---:|
| `clone_debt` | 23 | **19** |
| `au_adoption` | 39 | **38** |
| `component_adoption` | 39 | **38** |

## ⏫ Promotions — queued for one-pass approval

- **13** rule candidate(s) (L-1→L0) · **2** sentinel candidate(s) (L0→L2)
- 15 tracked · 0 still below the recurrence gate
- top rule: `rule:html:loads_utils_js`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
