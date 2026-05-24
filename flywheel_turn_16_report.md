# RAG Flywheel — Turn 16 report
Generated: 2026-05-21T19:18:22.744250+00:00

## Walk metrics
- Tiles observed   : **22** (22 real / 0 dry)
- Pages walked     : 7 (alert-hub=3, analytics=3, asset-hub=4, hive=3, inventory=3, pm-scheduler=3, skillmatrix=3)
- Routes used      : {'semantic': 22}
- Avg latency      : 5081.3 ms
- Avg tokens       : 1021.1

## Convergence metrics
- Grader pass rate    : **68.2%** (15/22)
- Checker pass rate   : **63.6%** (14/22)
- Citation coverage   : 63.6% (14/22 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **22**
- Tiles with checker FAIL (need work) : **8**
- Tiles with zero citations           : **8**

## Auto-actions taken
- canonical_sources INSERTed : **11**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_16_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:mtbf` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: __
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:on_track` — value=15 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._

## Tiles missing canonical anchor (auto-seeded above if --commit)

- `rag_tile:analytics:oee` — inferred source: `v_kpi_truth`
- `rag_tile:analytics:mtbf` — inferred source: `None`
- `rag_tile:analytics:pm_compliance` — inferred source: `v_pm_compliance_truth`
- `rag_tile:alert-hub:high_severity_alerts` — inferred source: `v_risk_truth`
- `rag_tile:alert-hub:anomaly_signals` — inferred source: `None`
- `rag_tile:alert-hub:amc_daily_brief` — inferred source: `None`
- `rag_tile:asset-hub:total_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:total_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:critical_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:pending_approval` — inferred source: `None`
- `rag_tile:pm-scheduler:overdue` — inferred source: `v_pm_scope_items_truth`
- `rag_tile:pm-scheduler:due_soon` — inferred source: `v_pm_compliance_truth`
- `rag_tile:pm-scheduler:on_track` — inferred source: `None`
- `rag_tile:inventory:out_of_stock` — inferred source: `v_inventory_items_truth`
- `rag_tile:inventory:low_stock` — inferred source: `v_inventory_items_truth`
- `rag_tile:inventory:pending_approval` — inferred source: `None`
- `rag_tile:skillmatrix:on_target` — inferred source: `None`
- `rag_tile:skillmatrix:quizzes_available` — inferred source: `None`
- `rag_tile:skillmatrix:total_badges` — inferred source: `None`
- `rag_tile:hive:maturity_stair` — inferred source: `None`
- `rag_tile:hive:adoption_health` — inferred source: `v_adoption_truth`
- `rag_tile:hive:open_issues` — inferred source: `None`
