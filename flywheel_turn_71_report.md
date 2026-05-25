# RAG Flywheel — Turn 71 report
Generated: 2026-05-24T11:16:30.715490+00:00

## Walk metrics
- Tiles observed   : **52** (52 real / 0 dry)
- Pages walked     : 9 (alert-hub=8, analytics=5, asset-hub=8, integrations=6, marketplace=5, ph-intelligence=4, pm-scheduler=4, predictive=7, project-manager=5)
- Routes used      : {'semantic': 36, 'n/a': 16}
- Avg latency      : 5863.7 ms
- Avg tokens       : 543.5

## Convergence metrics
- Grader pass rate    : **32.7%** (17/52)
- Checker pass rate   : **25.0%** (13/52)
- Citation coverage   : 32.7% (17/52 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **39**
- Tiles with zero citations           : **19**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_71_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:mtbf` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:pm_compliance` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:detail_panel` — value=4 rows — AI answer: __
- `analytics::analytics:results_panel` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:high_severity_alerts` — value=37 — AI answer: _The number reflects High-severity alerts, which are assets with a composite risk score of high or critical, sourced from_
- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:detail_panel` — value=4 rows — AI answer: __
- `alert-hub::alert-hub:amc_assets` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_pms` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_parts` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_crew` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:total_assets` — value=30 — AI answer: __
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: __
- `asset-hub::asset-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:logbook_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pm_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:last_failure` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:rcm_edges` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:overdue` — value=0 — AI answer: _The 'Overdue PMs' tile shows a non-zero value when there are preventive maintenance tasks past their due date. It reads _
- `pm-scheduler::pm-scheduler:due_soon` — value=19 — AI answer: __
- `pm-scheduler::pm-scheduler:on_track` — value=12 — AI answer: __
- `pm-scheduler::pm-scheduler:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:hot_assets` — value=2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:healthy_assets` — value=1 — AI answer: __
- `predictive::predictive:earliest_forecast` — value=1.2d — AI answer: __
- `predictive::predictive:risk_heatmap` — value= — AI answer: _the canonical source is listed in def#v_risk_truth_
- `predictive::predictive:mtbf_trend` — value=Weekly Failure Count — AI answer: __
- `integrations::integrations:active` — value=0 — AI answer: __
- `integrations::integrations:stale` — value=0 — AI answer: __
- `integrations::integrations:detail_panel` — value=4 rows — AI answer: _The number of rows in the 'Integrations detail' tile on the integrations.html page reflects the count of active integrat_
- `integrations::integrations:api_config` — value=Phase 5 · Intelligence API — AI answer: __
- `integrations::integrations:sync_log` — value=Tier 2 · Scheduled API Sync — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:current_tab` — value=— — AI answer: __
- `marketplace::marketplace:detail_panel` — value=4 rows — AI answer: __
- `ph-intelligence::ph-intelligence:top_failure_cause` — value=Wear — AI answer: __
- `project-manager::project-manager:project_list` — value=Project portfolio is climbing — a few things to handle2 past end_date. — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:active_projects` — value=4 — AI answer: __
