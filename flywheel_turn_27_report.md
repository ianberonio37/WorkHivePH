# RAG Flywheel — Turn 27 report
Generated: 2026-05-22T20:01:55.432260+00:00

## Walk metrics
- Tiles observed   : **48** (48 real / 0 dry)
- Pages walked     : 16 (achievements=3, alert-hub=3, analytics=3, asset-hub=3, dayplanner=3, hive=3, integrations=3, inventory=3, marketplace=3, ph-intelligence=3, pm-scheduler=3, predictive=3, project-manager=3, report-sender=3, shift-brain=3, skillmatrix=3)
- Routes used      : {'semantic': 44, 'cold_archive': 1, 'n/a': 3}
- Avg latency      : 3622.3 ms
- Avg tokens       : 1204.0

## Convergence metrics
- Grader pass rate    : **91.7%** (44/48)
- Checker pass rate   : **87.5%** (42/48)
- Citation coverage   : 89.6% (43/48 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **10**
- Tiles with checker FAIL (need work) : **6**
- Tiles with zero citations           : **2**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_27_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:oee` — value=— — AI answer: _The 'OEE (avg, partial)' on analytics.html measures Overall Equipment Effectiveness and reads from v_OEE_truth view._
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _To find the count of critical assets in v_asset_truth, you can query the view [def#v_asset_truth] with a filter on asset_
- `achievements::achievements:xp_this_week` — value=+600 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `dayplanner::dayplanner:today_count` — value=0 — AI answer: __
- `dayplanner::dayplanner:week_count` — value=6 — AI answer: __
- `dayplanner::dayplanner:overdue_count` — value=6 — AI answer: __

## Tiles missing canonical anchor (auto-seeded above if --commit)

- `rag_tile:achievements:xp_this_week` — inferred source: `None`
- `rag_tile:dayplanner:overdue_count` — inferred source: `None`
- `rag_tile:integrations:stale` — inferred source: `None`
- `rag_tile:integrations:disabled` — inferred source: `None`
- `rag_tile:ph-intelligence:plants_in_network` — inferred source: `None`
- `rag_tile:ph-intelligence:report_freshness` — inferred source: `None`
- `rag_tile:project-manager:on_hold_planning` — inferred source: `None`
- `rag_tile:report-sender:reports_selected` — inferred source: `None`
- `rag_tile:report-sender:recipients` — inferred source: `None`
- `rag_tile:report-sender:saved_contacts` — inferred source: `None`
