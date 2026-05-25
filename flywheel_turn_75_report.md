# RAG Flywheel — Turn 75 report
Generated: 2026-05-24T12:49:06.927774+00:00

## Walk metrics
- Tiles observed   : **40** (40 real / 0 dry)
- Pages walked     : 7 (alert-hub=8, analytics=5, asset-hub=8, hive=4, inventory=4, pm-scheduler=4, predictive=7)
- Routes used      : {'semantic': 39, 'n/a': 1}
- Avg latency      : 3997.5 ms
- Avg tokens       : 323.0

## Convergence metrics
- Grader pass rate    : **0.0%** (0/40)
- Checker pass rate   : **0.0%** (0/40)
- Citation coverage   : 0.0% (0/40 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **40**
- Tiles with zero citations           : **39**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_75_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:oee` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:mtbf` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:pm_compliance` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:results_panel` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:high_severity_alerts` — value=37 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_assets` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_pms` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_parts` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_crew` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:total_assets` — value=30 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:logbook_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pm_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:last_failure` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:rcm_edges` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:overdue` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:due_soon` — value=19 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:on_track` — value=12 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:hot_assets` — value=2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:healthy_assets` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:earliest_forecast` — value=1.2d — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:risk_ranking` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:risk_heatmap` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:mtbf_trend` — value=Weekly Failure Count — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:out_of_stock` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:low_stock` — value=3 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: __
- `hive::hive:adoption_health` — value=Healthy — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:open_issues` — value=21 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
