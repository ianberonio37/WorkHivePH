# RAG Flywheel — Turn 25 report
Generated: 2026-05-22T07:49:26.686739+00:00

## Walk metrics
- Tiles observed   : **48** (48 real / 0 dry)
- Pages walked     : 16 (achievements=3, alert-hub=3, analytics=3, asset-hub=3, dayplanner=3, hive=3, integrations=3, inventory=3, marketplace=3, ph-intelligence=3, pm-scheduler=3, predictive=3, project-manager=3, report-sender=3, shift-brain=3, skillmatrix=3)
- Routes used      : {'semantic': 42, 'cold_archive': 1, 'n/a': 5}
- Avg latency      : 3226.0 ms
- Avg tokens       : 848.4

## Convergence metrics
- Grader pass rate    : **79.2%** (38/48)
- Checker pass rate   : **79.2%** (38/48)
- Citation coverage   : 77.1% (37/48 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **10**
- Tiles with checker FAIL (need work) : **10**
- Tiles with zero citations           : **6**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_25_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:low_stock` — value=3 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:open_issues` — value=21 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:xp_this_week` — value=+600 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:recipients` — value=0 — AI answer: __
- `report-sender::report-sender:saved_contacts` — value=0 — AI answer: __
- `shift-brain::shift-brain:top_risk_this_shift` — value=0 — AI answer: __
- `shift-brain::shift-brain:pms_due` — value=0 — AI answer: __
- `shift-brain::shift-brain:carry_forward` — value=0 — AI answer: __

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
