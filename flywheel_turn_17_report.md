# RAG Flywheel — Turn 17 report
Generated: 2026-05-21T19:31:53.237775+00:00

## Walk metrics
- Tiles observed   : **26** (26 real / 0 dry)
- Pages walked     : 8 (alert-hub=3, analytics=3, asset-hub=3, hive=5, inventory=3, pm-scheduler=3, predictive=3, skillmatrix=3)
- Routes used      : {'semantic': 26}
- Avg latency      : 8676.9 ms
- Avg tokens       : 1104.8

## Convergence metrics
- Grader pass rate    : **84.6%** (22/26)
- Checker pass rate   : **84.6%** (22/26)
- Citation coverage   : 73.1% (19/26 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **26**
- Tiles with checker FAIL (need work) : **4**
- Tiles with zero citations           : **7**

## Auto-actions taken
- canonical_sources INSERTed : **17**
- New L0 tile locks added    : **3**
- L2 review queue            : `.tmp/flywheel_turn_17_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:earliest_forecast` — value=1.2d — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:open_issues` — value=21 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._

## Tiles missing canonical anchor (auto-seeded above if --commit)

- `rag_tile:analytics:oee` — inferred source: `None`
- `rag_tile:analytics:mtbf` — inferred source: `v_kpi_truth`
- `rag_tile:analytics:pm_compliance` — inferred source: `v_pm_compliance_truth`
- `rag_tile:alert-hub:high_severity_alerts` — inferred source: `v_risk_truth`
- `rag_tile:alert-hub:anomaly_signals` — inferred source: `v_anomaly_truth`
- `rag_tile:alert-hub:amc_daily_brief` — inferred source: `None`
- `rag_tile:asset-hub:total_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:critical_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:pending_approval` — inferred source: `None`
- `rag_tile:pm-scheduler:overdue` — inferred source: `v_pm_scope_items_truth`
- `rag_tile:pm-scheduler:due_soon` — inferred source: `v_pm_compliance_truth`
- `rag_tile:pm-scheduler:on_track` — inferred source: `logbook`
- `rag_tile:predictive:hot_assets` — inferred source: `v_risk_truth`
- `rag_tile:predictive:healthy_assets` — inferred source: `v_pm_compliance_truth`
- `rag_tile:predictive:earliest_forecast` — inferred source: `None`
- `rag_tile:inventory:out_of_stock` — inferred source: `v_inventory_items_truth`
- `rag_tile:inventory:low_stock` — inferred source: `v_inventory_items_truth`
- `rag_tile:inventory:pending_approval` — inferred source: `v_inventory_items_truth`
- `rag_tile:skillmatrix:on_target` — inferred source: `None`
- `rag_tile:skillmatrix:quizzes_available` — inferred source: `None`
- `rag_tile:skillmatrix:total_badges` — inferred source: `v_worker_skill_truth`
- `rag_tile:hive:maturity_stair` — inferred source: `None`
- `rag_tile:hive:adoption_health` — inferred source: `v_pm_compliance_truth`
- `rag_tile:hive:maturity_stair` — inferred source: `None`
- `rag_tile:hive:adoption_health` — inferred source: `v_asset_truth`
- `rag_tile:hive:open_issues` — inferred source: `None`
