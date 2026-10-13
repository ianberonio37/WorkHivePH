# Flywheel Turn #485

_2026-10-13T23:16:58_

## Layer deltas

| Layer | Metric | Before | After | Delta |
|---|---|---:|---:|---:|
| L-1   | cluster proposals       | 0 | 0 | · |
| L-1.5 | rules in manifest       | 50 | 50 | · |
| L0    | baselines tracked       | 213 | 214 | +1 ✅ |
| L0    | total locked count      | 3810 | 3804 | ↓6 ✅ |
| L2    | sentinel parity cases   | 29 | 29 | · |
| L13   | stale walkthroughs      | 0 | 0 | · |

## ✅ Ratchets (3) — baselines tightened

| Validator | Was | Now |
|---|---:|---:|
| `design_detector` | 87 | **82** |
| `canonical_anchor` | 5 | **4** |
| `design_tokens` | 144 | **143** |

## 🟡 Quarantined (1) — baseline deltas classified as noise, not scored (env up)

| Validator | Was | Now | Class | Note |
|---|---:|---:|---|---|
| `db_adoption` | 244 | 245 | **adoption-ratchet** |  |

## ⏫ Promotions — queued for one-pass approval

- **13** rule candidate(s) (L-1→L0) · **2** sentinel candidate(s) (L0→L2)
- 15 tracked · 0 still below the recurrence gate
- top rule: `rule:html:loads_utils_js`
- top sentinel: `sentinel:user_facing_jargon`
- See **[promotion_queue.md](promotion_queue.md)** for the full ranked queue + draft stubs.
