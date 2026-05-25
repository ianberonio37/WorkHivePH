# RAG Flywheel — Turn 72 report
Generated: 2026-05-24T11:57:15.514183+00:00

## Walk metrics
- Tiles observed   : **61** (61 real / 0 dry)
- Pages walked     : 12 (achievements=7, analytics=5, asset-hub=8, hive=4, inventory=4, marketplace=5, pm-scheduler=4, predictive=7, project-manager=5, report-sender=4, shift-brain=4, skillmatrix=4)
- Routes used      : {'semantic': 36, 'n/a': 25}
- Avg latency      : 5077.9 ms
- Avg tokens       : 405.0

## Convergence metrics
- Grader pass rate    : **14.8%** (9/61)
- Checker pass rate   : **13.1%** (8/61)
- Citation coverage   : 13.1% (8/61 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **53**
- Tiles with zero citations           : **28**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_72_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:mtbf` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:pm_compliance` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:detail_panel` — value=4 rows — AI answer: __
- `analytics::analytics:results_panel` — value= — AI answer: __
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: __
- `asset-hub::asset-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:logbook_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pm_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:last_failure` — value= — AI answer: __
- `asset-hub::asset-hub:rcm_edges` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:on_track` — value=12 — AI answer: __
- `pm-scheduler::pm-scheduler:detail_panel` — value=4 rows — AI answer: __
- `predictive::predictive:hot_assets` — value=2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:earliest_forecast` — value=1.2d — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:detail_panel` — value=4 rows — AI answer: __
- `predictive::predictive:risk_ranking` — value=4 rows — AI answer: _the Risk ranking table reflects the latest risk score per asset, [def#v_risk_truth] [def view v_risk_truth]._
- `predictive::predictive:risk_heatmap` — value= — AI answer: __
- `predictive::predictive:mtbf_trend` — value=Weekly Failure Count — AI answer: __
- `inventory::inventory:out_of_stock` — value=0 — AI answer: __
- `inventory::inventory:low_stock` — value=3 — AI answer: __
- `inventory::inventory:pending_approval` — value=0 — AI answer: __
- `inventory::inventory:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:on_target` — value=5/5 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: __
- `skillmatrix::skillmatrix:detail_panel` — value=4 rows — AI answer: __
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: __
- `hive::hive:adoption_health` — value=Healthy — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:open_issues` — value=21 — AI answer: __
- `hive::hive:detail_panel` — value=4 rows — AI answer: __
- `achievements::achievements:xp_this_week` — value=+655 — AI answer: __
- `achievements::achievements:active_domains` — value=3/12 — AI answer: __
- `achievements::achievements:total_level` — value=71 — AI answer: __
- `achievements::achievements:detail_panel` — value=4 rows — AI answer: __
- `achievements::achievements:composite_score` — value= — AI answer: __
- `achievements::achievements:active_domains_stat` — value= — AI answer: __
- `achievements::achievements:top_domain` — value= — AI answer: __
- `marketplace::marketplace:current_tab` — value=Parts — AI answer: __
- `marketplace::marketplace:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:listing_grid` — value=13 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:project_list` — value=Project portfolio is climbing — a few things to handle2 past end_date. — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:active_projects` — value=4 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:past_end_date` — value=2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:on_hold_planning` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:project_cards` — value=SHD-2026-001 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:reports_selected` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:recipients` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:saved_contacts` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:top_risk_this_shift` — value=5 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:pms_due` — value=22 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:carry_forward` — value=18 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:detail_panel` — value=5 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
