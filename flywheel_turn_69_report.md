# RAG Flywheel — Turn 69 report
Generated: 2026-05-24T10:08:53.789991+00:00

## Walk metrics
- Tiles observed   : **9** (9 real / 0 dry)
- Pages walked     : 2 (pm-scheduler=4, project-manager=5)
- Routes used      : {'semantic': 6, 'n/a': 3}
- Avg latency      : 6680.6 ms
- Avg tokens       : 882.9

## Convergence metrics
- Grader pass rate    : **66.7%** (6/9)
- Checker pass rate   : **55.6%** (5/9)
- Citation coverage   : 66.7% (6/9 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **4**
- Tiles with zero citations           : **0**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_69_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `pm-scheduler::pm-scheduler:due_soon` — value=19 — AI answer: _The number 19 reflects the count of preventive maintenance tasks coming due in the next 14 days, sourced from v_pm_compl_
- `pm-scheduler::pm-scheduler:on_track` — value=12 — AI answer: __
- `pm-scheduler::pm-scheduler:detail_panel` — value=4 rows — AI answer: __
- `project-manager::project-manager:project_cards` — value=SHD-2026-001 — AI answer: __
