# RAG Flywheel — Turn 19 report
Generated: 2026-05-21T19:46:07.508471+00:00

## Walk metrics
- Tiles observed   : **26** (26 real / 0 dry)
- Pages walked     : 7 (alert-hub=3, analytics=3, asset-hub=6, hive=5, inventory=3, pm-scheduler=3, skillmatrix=3)
- Routes used      : {'semantic': 25, 'n/a': 1}
- Avg latency      : 8969.9 ms
- Avg tokens       : 1079.2

## Convergence metrics
- Grader pass rate    : **73.1%** (19/26)
- Checker pass rate   : **65.4%** (17/26)
- Citation coverage   : 65.4% (17/26 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **26**
- Tiles with checker FAIL (need work) : **9**
- Tiles with zero citations           : **8**

## Auto-actions taken
- canonical_sources INSERTed : **17**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_19_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `alert-hub::alert-hub:high_severity_alerts` — value=36 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _The "Critical assets" tile should reflect the number of assets whose asset_criticality flag is true in the canonical ass_
- `pm-scheduler::pm-scheduler:on_track` — value=15 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: _Source view v_worker_skill_truth is used for skill matrix, shift planner, analytics roll-ups, and AMC Crew-Builder assig_
- `hive::hive:adoption_health` — value=Healthy — AI answer: __
- `hive::hive:adoption_health` — value=Healthy — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:open_issues` — value=21 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._

## Tiles missing canonical anchor (auto-seeded above if --commit)

- `rag_tile:analytics:oee` — inferred source: `v_kpi_truth`
- `rag_tile:analytics:mtbf` — inferred source: `v_kpi_truth`
- `rag_tile:analytics:pm_compliance` — inferred source: `v_pm_compliance_truth`
- `rag_tile:alert-hub:high_severity_alerts` — inferred source: `None`
- `rag_tile:alert-hub:anomaly_signals` — inferred source: `None`
- `rag_tile:alert-hub:amc_daily_brief` — inferred source: `v_amc_truth`
- `rag_tile:asset-hub:total_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:critical_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:pending_approval` — inferred source: `None`
- `rag_tile:asset-hub:total_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:critical_assets` — inferred source: `v_inventory_items_truth`
- `rag_tile:asset-hub:pending_approval` — inferred source: `None`
- `rag_tile:pm-scheduler:overdue` — inferred source: `v_pm_compliance_truth`
- `rag_tile:pm-scheduler:due_soon` — inferred source: `v_pm_compliance_truth`
- `rag_tile:pm-scheduler:on_track` — inferred source: `None`
- `rag_tile:inventory:out_of_stock` — inferred source: `v_inventory_items_truth`
- `rag_tile:inventory:low_stock` — inferred source: `v_inventory_items_truth`
- `rag_tile:inventory:pending_approval` — inferred source: `v_marketplace_inquiries_truth`
- `rag_tile:skillmatrix:on_target` — inferred source: `v_worker_skill_truth`
- `rag_tile:skillmatrix:quizzes_available` — inferred source: `None`
- `rag_tile:skillmatrix:total_badges` — inferred source: `v_worker_skill_truth`
- `rag_tile:hive:maturity_stair` — inferred source: `logbook`
- `rag_tile:hive:adoption_health` — inferred source: `None`
- `rag_tile:hive:maturity_stair` — inferred source: `v_pm_compliance_truth`
- `rag_tile:hive:adoption_health` — inferred source: `None`
- `rag_tile:hive:open_issues` — inferred source: `None`
