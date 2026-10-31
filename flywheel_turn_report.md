# Flywheel Turn #497

_2026-10-31T14:25:55_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 217 | 217 | · |
| L0    | total locked count      | 3561 | 3557 | ↓4 ✅ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## ✅ Ratchets (1) — baselines tightened

| Validator | Was | Now |
|---|---:|---:|
| `clone_debt` | 28 | **23** |

## 🟡 Quarantined (1) — baseline deltas classified as noise, not scored (env up)

| Validator | Was | Now | Class | Note |
|---|---:|---:|---|---|
| `db_adoption` | 248 | 249 | **adoption-ratchet** |  |

## ⏫ Promotions — queued for one-pass approval

- **13** rule candidate(s) (L-1→L0) · **2** sentinel candidate(s) (L0→L2)
- 15 tracked · 0 still below the recurrence gate
- top rule: `rule:html:loads_utils_js`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
