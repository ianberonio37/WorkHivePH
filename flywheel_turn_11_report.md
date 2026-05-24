# RAG Flywheel — Turn 11 report
Generated: 2026-05-21T18:57:00.278966+00:00

## Walk metrics
- Tiles observed   : **21** (21 real / 0 dry)
- Pages walked     : 7 (alert-hub=3, analytics=3, asset-hub=3, hive=3, inventory=3, pm-scheduler=3, skillmatrix=3)
- Routes used      : {'semantic': 20, 'n/a': 1}
- Avg latency      : 3983.3 ms
- Avg tokens       : 1434.5

## Convergence metrics
- Grader pass rate    : **61.9%** (13/21)
- Checker pass rate   : **38.1%** (8/21)
- Citation coverage   : 52.4% (11/21 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **21**
- Tiles with checker FAIL (need work) : **13**
- Tiles with zero citations           : **9**

## Auto-actions taken
- canonical_sources INSERTed : **9**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_11_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `alert-hub::alert-hub:high_severity_alerts` — value=36 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: _The definition of 'Anomaly signals' KPI on the alert-hub.html page is not provided in the given chunks. However, based o_
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: _The data source for the 'AMC daily brief' tile on alert-hub.html is the v_amc_briefings view [def#amc_briefings]. The co_
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:on_track` — value=15 — AI answer: _The definition of 'On track' is not found in the provided chunks. The source of the number 15 is also not found._
- `inventory::inventory:low_stock` — value=3 — AI answer: __
- `inventory::inventory:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:on_target` — value=5/5 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:adoption_health` — value=Healthy — AI answer: _The provided chunks do not contain enough information to determine the specific metrics and data sources used to calcula_
- `hive::hive:open_issues` — value=21 — AI answer: _The specific maintenance records or views related to the 'Open issues' tile count on hive.html are not explicitly stated_

## Tiles missing canonical anchor (auto-seeded above if --commit)

- `rag_tile:analytics:oee` — inferred source: `None`
- `rag_tile:analytics:mtbf` — inferred source: `v_kpi_truth`
- `rag_tile:analytics:pm_compliance` — inferred source: `v_pm_compliance_truth`
- `rag_tile:alert-hub:high_severity_alerts` — inferred source: `None`
- `rag_tile:alert-hub:anomaly_signals` — inferred source: `v_risk_truth`
- `rag_tile:alert-hub:amc_daily_brief` — inferred source: `amc_briefings`
- `rag_tile:asset-hub:total_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:critical_assets` — inferred source: `None`
- `rag_tile:asset-hub:pending_approval` — inferred source: `None`
- `rag_tile:pm-scheduler:overdue` — inferred source: `v_pm_compliance_truth`
- `rag_tile:pm-scheduler:due_soon` — inferred source: `v_pm_compliance_truth`
- `rag_tile:pm-scheduler:on_track` — inferred source: `None`
- `rag_tile:inventory:out_of_stock` — inferred source: `v_inventory_items_truth`
- `rag_tile:inventory:low_stock` — inferred source: `None`
- `rag_tile:inventory:pending_approval` — inferred source: `None`
- `rag_tile:skillmatrix:on_target` — inferred source: `None`
- `rag_tile:skillmatrix:quizzes_available` — inferred source: `None`
- `rag_tile:skillmatrix:total_badges` — inferred source: `None`
- `rag_tile:hive:maturity_stair` — inferred source: `None`
- `rag_tile:hive:adoption_health` — inferred source: `None`
- `rag_tile:hive:open_issues` — inferred source: `pm_completions`
