# RAG Flywheel — Turn 3 report
Generated: 2026-05-21T11:33:27.062480+00:00

## Walk metrics
- Tiles observed   : **21** (21 real / 0 dry)
- Pages walked     : 7 (alert-hub=3, analytics=3, asset-hub=3, hive=3, inventory=3, pm-scheduler=3, skillmatrix=3)
- Routes used      : {'semantic': 21}
- Avg latency      : 4344.2 ms
- Avg tokens       : 1357.4

## Convergence metrics
- Grader pass rate    : **28.6%** (6/21)
- Checker pass rate   : **19.0%** (4/21)
- Citation coverage   : 14.3% (3/21 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **21**
- Tiles with checker FAIL (need work) : **17**
- Tiles with zero citations           : **18**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **21**
- L2 review queue            : `.tmp/flywheel_turn_3_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:oee` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:mtbf` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:pm_compliance` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:total_assets` — value=30 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:overdue` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:due_soon` — value=15 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:out_of_stock` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:on_target` — value=5/5 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: _The criteria for determining Hive maturity stair level and its relation to maintenance records are not specified in the _
- `hive::hive:adoption_health` — value=Healthy — AI answer: _The specific metrics or criteria used to determine the 'Adoption health' status on hive.html are not provided. Therefore_

## Tiles missing canonical anchor (auto-seeded above if --commit)

- `rag_tile:analytics:oee` — inferred source: `None`
- `rag_tile:analytics:mtbf` — inferred source: `None`
- `rag_tile:analytics:pm_compliance` — inferred source: `None`
- `rag_tile:alert-hub:high_severity_alerts` — inferred source: `None`
- `rag_tile:alert-hub:anomaly_signals` — inferred source: `None`
- `rag_tile:alert-hub:amc_daily_brief` — inferred source: `None`
- `rag_tile:asset-hub:total_assets` — inferred source: `None`
- `rag_tile:asset-hub:critical_assets` — inferred source: `None`
- `rag_tile:asset-hub:pending_approval` — inferred source: `None`
- `rag_tile:pm-scheduler:overdue` — inferred source: `None`
- `rag_tile:pm-scheduler:due_soon` — inferred source: `None`
- `rag_tile:pm-scheduler:on_track` — inferred source: `None`
- `rag_tile:inventory:out_of_stock` — inferred source: `None`
- `rag_tile:inventory:low_stock` — inferred source: `None`
- `rag_tile:inventory:pending_approval` — inferred source: `None`
- `rag_tile:skillmatrix:on_target` — inferred source: `None`
- `rag_tile:skillmatrix:quizzes_available` — inferred source: `None`
- `rag_tile:skillmatrix:total_badges` — inferred source: `None`
- `rag_tile:hive:maturity_stair` — inferred source: `None`
- `rag_tile:hive:adoption_health` — inferred source: `None`
- `rag_tile:hive:open_issues` — inferred source: `None`
