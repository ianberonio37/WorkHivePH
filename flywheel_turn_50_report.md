# RAG Flywheel — Turn 50 report
Generated: 2026-05-23T22:32:04.235922+00:00

## Walk metrics
- Tiles observed   : **83** (83 real / 0 dry)
- Pages walked     : 16 (achievements=7, alert-hub=8, analytics=5, asset-hub=8, dayplanner=4, hive=4, integrations=6, inventory=4, marketplace=5, ph-intelligence=4, pm-scheduler=4, predictive=7, project-manager=5, report-sender=4, shift-brain=4, skillmatrix=4)
- Routes used      : {'semantic': 68, 'n/a': 14, 'simple_recency': 1}
- Avg latency      : 2964.6 ms
- Avg tokens       : 622.4

## Convergence metrics
- Grader pass rate    : **38.6%** (32/83)
- Checker pass rate   : **24.1%** (20/83)
- Citation coverage   : 37.3% (31/83 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **63**
- Tiles with zero citations           : **38**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_50_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_pms` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_parts` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_crew` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: __
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: _The 'Pending approval' tile shows a non-zero value when there are assets in the 'pending approval' state. The canonical _
- `asset-hub::asset-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:logbook_count` — value= — AI answer: __
- `asset-hub::asset-hub:last_failure` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:due_soon` — value=18 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:healthy_assets` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:risk_ranking` — value=4 rows — AI answer: __
- `predictive::predictive:risk_heatmap` — value= — AI answer: __
- `predictive::predictive:mtbf_trend` — value=Weekly Failure Count — AI answer: __
- `inventory::inventory:low_stock` — value=3 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:pending_approval` — value=0 — AI answer: __
- `inventory::inventory:detail_panel` — value=4 rows — AI answer: _The 4 rows in the 'Inventory detail breakdown' tile reflect active inventory items tracked via the canonical view v_inve_
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: __
- `skillmatrix::skillmatrix:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: _the canonical source is listed in [def#v_pm_compliance_truth] and [def#v_asset_truth] for 'Hive maturity stair' tile, bu_
- `hive::hive:adoption_health` — value=Healthy — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:open_issues` — value=21 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:detail_panel` — value=4 rows — AI answer: _The number of rows in the 'Hive supervisor detail' tile on the hive.html page reflects the number of assets with pending_
- `achievements::achievements:active_domains` — value=3/12 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:total_level` — value=71 — AI answer: __
- `achievements::achievements:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:composite_score` — value= — AI answer: _the canonical source is listed in [def#v_hive_readiness_truth]_
- `achievements::achievements:active_domains_stat` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `dayplanner::dayplanner:week_count` — value=6 — AI answer: __
- `dayplanner::dayplanner:overdue_count` — value=6 — AI answer: _The 'Overdue tasks' tile on the dayplanner.html page reflects overdue schedule items past their due date and not yet mar_
- `dayplanner::dayplanner:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:active` — value=0 — AI answer: _The 'Active integrations' tile shows a non-zero value when there are active integrations. The canonical source view is v_
- `integrations::integrations:stale` — value=0 — AI answer: __
- `integrations::integrations:disabled` — value=0 — AI answer: __
- `integrations::integrations:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:api_config` — value=Phase 5 · Intelligence API — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:sync_log` — value=Tier 2 · Scheduled API Sync — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:listings_in_view` — value=13 — AI answer: _the canonical source is listed in [def#v_marketplace_sellers_truth] [def#v_kpi_truth] [def#marketplace_listings]_
- `marketplace::marketplace:my_listings` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:current_tab` — value=Parts — AI answer: __
- `marketplace::marketplace:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:listing_grid` — value=13 rows — AI answer: __
- `ph-intelligence::ph-intelligence:plants_in_network` — value=3 — AI answer: _The 'Plants in network' tile reflects the count of hives contributing anonymized data to cross-network benchmarks. This _
- `ph-intelligence::ph-intelligence:top_failure_cause` — value=Wear — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `ph-intelligence::ph-intelligence:report_freshness` — value=4d — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `ph-intelligence::ph-intelligence:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:project_list` — value=Project portfolio is climbing — a few things to handle2 past end_date. — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:active_projects` — value=4 — AI answer: _The number reflects active Capex / shutdown / contractor / workorder projects per hive._
- `project-manager::project-manager:past_end_date` — value=2 — AI answer: _The provided chunks do not contain information about the 'Past end date' tile or its data source. No maintenance records_
- `project-manager::project-manager:on_hold_planning` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:project_cards` — value=SHD-2026-001 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:reports_selected` — value=0 — AI answer: _The 'Reports selected' tile on the report-sender.html page will show a non-zero value when the user has ticked reports t_
- `report-sender::report-sender:recipients` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:saved_contacts` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:top_risk_this_shift` — value=0 — AI answer: __
- `shift-brain::shift-brain:pms_due` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:carry_forward` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:detail_panel` — value=5 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
