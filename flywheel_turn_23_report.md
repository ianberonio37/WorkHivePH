# RAG Flywheel — Turn 23 report
Generated: 2026-05-22T07:28:24.740480+00:00

## Walk metrics
- Tiles observed   : **26** (26 real / 0 dry)
- Pages walked     : 8 (alert-hub=2, analytics=3, asset-hub=4, hive=3, inventory=3, pm-scheduler=3, predictive=5, skillmatrix=3)
- Routes used      : {'semantic': 22, 'n/a': 4}
- Avg latency      : 9064.6 ms
- Avg tokens       : 1142.2

## Convergence metrics
- Grader pass rate    : **65.4%** (17/26)
- Checker pass rate   : **53.8%** (14/26)
- Citation coverage   : 61.5% (16/26 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **26**
- Tiles with checker FAIL (need work) : **12**
- Tiles with zero citations           : **6**

## Auto-actions taken
- canonical_sources INSERTed : **12**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_23_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:oee` — value=— — AI answer: _Overall Equipment Effectiveness_
- `analytics::analytics:mtbf` — value=— — AI answer: _Mean Time Between Failures (MTBF) for a machine within a user-selected window_
- `analytics::analytics:pm_compliance` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:high_severity_alerts` — value=36 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:on_track` — value=15 — AI answer: _PM compliance (30d approx) KPI_
- `predictive::predictive:earliest_forecast` — value=1.2d — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:low_stock` — value=3 — AI answer: __
- `inventory::inventory:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:on_target` — value=5/5 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: __
- `hive::hive:adoption_health` — value=Healthy — AI answer: __
- `hive::hive:open_issues` — value=21 — AI answer: __

## Tiles missing canonical anchor (auto-seeded above if --commit)

- `rag_tile:analytics:oee` — inferred source: `None`
- `rag_tile:analytics:mtbf` — inferred source: `None`
- `rag_tile:analytics:pm_compliance` — inferred source: `None`
- `rag_tile:alert-hub:high_severity_alerts` — inferred source: `None`
- `rag_tile:alert-hub:anomaly_signals` — inferred source: `v_anomaly_truth`
- `rag_tile:asset-hub:total_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:critical_assets` — inferred source: `v_inventory_items_truth`
- `rag_tile:asset-hub:total_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:critical_assets` — inferred source: `None`
- `rag_tile:pm-scheduler:overdue` — inferred source: `None`
- `rag_tile:pm-scheduler:due_soon` — inferred source: `v_pm_compliance_truth`
- `rag_tile:pm-scheduler:on_track` — inferred source: `None`
- `rag_tile:predictive:hot_assets` — inferred source: `v_risk_truth`
- `rag_tile:predictive:healthy_assets` — inferred source: `v_risk_truth`
- `rag_tile:predictive:earliest_forecast` — inferred source: `None`
- `rag_tile:predictive:hot_assets` — inferred source: `v_asset_truth`
- `rag_tile:predictive:healthy_assets` — inferred source: `logbook`
- `rag_tile:inventory:out_of_stock` — inferred source: `v_inventory_items_truth`
- `rag_tile:inventory:low_stock` — inferred source: `None`
- `rag_tile:inventory:pending_approval` — inferred source: `None`
- `rag_tile:skillmatrix:on_target` — inferred source: `None`
- `rag_tile:skillmatrix:quizzes_available` — inferred source: `logbook`
- `rag_tile:skillmatrix:total_badges` — inferred source: `v_worker_skill_truth`
- `rag_tile:hive:maturity_stair` — inferred source: `None`
- `rag_tile:hive:adoption_health` — inferred source: `None`
- `rag_tile:hive:open_issues` — inferred source: `None`
