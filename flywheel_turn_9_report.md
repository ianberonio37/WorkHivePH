# RAG Flywheel — Turn 9 report
Generated: 2026-05-21T11:52:26.069302+00:00

## Walk metrics
- Tiles observed   : **21** (21 real / 0 dry)
- Pages walked     : 7 (alert-hub=3, analytics=3, asset-hub=3, hive=3, inventory=3, pm-scheduler=3, skillmatrix=3)
- Routes used      : {'semantic': 21}
- Avg latency      : 4605.8 ms
- Avg tokens       : 1268.0

## Convergence metrics
- Grader pass rate    : **81.0%** (17/21)
- Checker pass rate   : **71.4%** (15/21)
- Citation coverage   : 76.2% (16/21 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **21**
- Tiles with checker FAIL (need work) : **6**
- Tiles with zero citations           : **5**

## Auto-actions taken
- canonical_sources INSERTed : **16**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_9_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:due_soon` — value=15 — AI answer: _The provided chunks do not contain enough information to answer the question._
- `inventory::inventory:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:adoption_health` — value=Healthy — AI answer: _The Adoption health tile on the hive.html page is directly contributed by logbook rows or canonical views such as v_logb_

## Tiles missing canonical anchor (auto-seeded above if --commit)

- `rag_tile:analytics:oee` — inferred source: `v_kpi_truth`
- `rag_tile:analytics:mtbf` — inferred source: `v_kpi_truth`
- `rag_tile:analytics:pm_compliance` — inferred source: `v_pm_compliance_truth`
- `rag_tile:alert-hub:high_severity_alerts` — inferred source: `v_risk_truth`
- `rag_tile:alert-hub:anomaly_signals` — inferred source: `v_anomaly_truth`
- `rag_tile:alert-hub:amc_daily_brief` — inferred source: `v_amc_truth`
- `rag_tile:asset-hub:total_assets` — inferred source: `v_asset_truth`
- `rag_tile:asset-hub:critical_assets` — inferred source: `None`
- `rag_tile:asset-hub:pending_approval` — inferred source: `None`
- `rag_tile:pm-scheduler:overdue` — inferred source: `v_pm_compliance_truth`
- `rag_tile:pm-scheduler:due_soon` — inferred source: `None`
- `rag_tile:pm-scheduler:on_track` — inferred source: `v_pm_compliance_truth`
- `rag_tile:inventory:out_of_stock` — inferred source: `v_inventory_items_truth`
- `rag_tile:inventory:low_stock` — inferred source: `v_inventory_items_truth`
- `rag_tile:inventory:pending_approval` — inferred source: `None`
- `rag_tile:skillmatrix:on_target` — inferred source: `v_worker_skill_truth`
- `rag_tile:skillmatrix:quizzes_available` — inferred source: `v_worker_skill_truth`
- `rag_tile:skillmatrix:total_badges` — inferred source: `None`
- `rag_tile:hive:maturity_stair` — inferred source: `v_pm_compliance_truth`
- `rag_tile:hive:adoption_health` — inferred source: `v_logbook_truth`
- `rag_tile:hive:open_issues` — inferred source: `v_logbook_truth`
