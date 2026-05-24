# RAG Flywheel — Turn 18 report
Generated: 2026-05-21T19:38:24.087987+00:00

## Walk metrics
- Tiles observed   : **24** (24 real / 0 dry)
- Pages walked     : 7 (alert-hub=6, analytics=3, asset-hub=3, hive=3, inventory=3, pm-scheduler=3, skillmatrix=3)
- Routes used      : {'semantic': 24}
- Avg latency      : 7719.2 ms
- Avg tokens       : 1056.3

## Convergence metrics
- Grader pass rate    : **75.0%** (18/24)
- Checker pass rate   : **70.8%** (17/24)
- Citation coverage   : 62.5% (15/24 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **24**
- Tiles with checker FAIL (need work) : **7**
- Tiles with zero citations           : **9**

## Auto-actions taken
- canonical_sources INSERTed : **14**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_18_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:mtbf` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: _The 'AMC daily brief' tile is showing None today on the alert-hub.html page because there are no high-severity alerts [d_
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:low_stock` — value=3 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:adoption_health` — value=Healthy — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._

## Tiles missing canonical anchor (auto-seeded above if --commit)

- `rag_tile:analytics:oee` — inferred source: `v_kpi_truth`
- `rag_tile:analytics:mtbf` — inferred source: `None`
- `rag_tile:analytics:pm_compliance` — inferred source: `v_pm_compliance_truth`
- `rag_tile:alert-hub:high_severity_alerts` — inferred source: `v_risk_truth`
- `rag_tile:alert-hub:anomaly_signals` — inferred source: `v_anomaly_truth`
- `rag_tile:alert-hub:amc_daily_brief` — inferred source: `None`
- `rag_tile:alert-hub:high_severity_alerts` — inferred source: `v_risk_truth`
- `rag_tile:alert-hub:anomaly_signals` — inferred source: `v_anomaly_truth`
- `rag_tile:alert-hub:amc_daily_brief` — inferred source: `None`
- `rag_tile:asset-hub:total_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:critical_assets` — inferred source: `v_logbook_truth`
- `rag_tile:asset-hub:pending_approval` — inferred source: `None`
- `rag_tile:pm-scheduler:overdue` — inferred source: `v_pm_compliance_truth`
- `rag_tile:pm-scheduler:due_soon` — inferred source: `v_pm_compliance_truth`
- `rag_tile:pm-scheduler:on_track` — inferred source: `v_pm_compliance_truth`
- `rag_tile:inventory:out_of_stock` — inferred source: `v_inventory_items_truth`
- `rag_tile:inventory:low_stock` — inferred source: `None`
- `rag_tile:inventory:pending_approval` — inferred source: `None`
- `rag_tile:skillmatrix:on_target` — inferred source: `v_worker_skill_truth`
- `rag_tile:skillmatrix:quizzes_available` — inferred source: `None`
- `rag_tile:skillmatrix:total_badges` — inferred source: `None`
- `rag_tile:hive:maturity_stair` — inferred source: `None`
- `rag_tile:hive:adoption_health` — inferred source: `None`
- `rag_tile:hive:open_issues` — inferred source: `v_pm_compliance_truth`
