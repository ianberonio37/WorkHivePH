# RAG Flywheel — Turn 61 report
Generated: 2026-05-24T05:23:52.270748+00:00

## Walk metrics
- Tiles observed   : **83** (83 real / 0 dry)
- Pages walked     : 16 (achievements=7, alert-hub=8, analytics=5, asset-hub=8, dayplanner=4, hive=4, integrations=6, inventory=4, marketplace=5, ph-intelligence=4, pm-scheduler=4, predictive=7, project-manager=5, report-sender=4, shift-brain=4, skillmatrix=4)
- Routes used      : {'semantic': 58, 'n/a': 24, 'simple_recency': 1}
- Avg latency      : 2278.9 ms
- Avg tokens       : 303.9

## Convergence metrics
- Grader pass rate    : **8.4%** (7/83)
- Checker pass rate   : **3.6%** (3/83)
- Citation coverage   : 8.4% (7/83 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **80**
- Tiles with zero citations           : **52**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_61_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:pm_compliance` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:detail_panel` — value=4 rows — AI answer: __
- `analytics::analytics:results_panel` — value= — AI answer: __
- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: __
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: __
- `alert-hub::alert-hub:detail_panel` — value=4 rows — AI answer: __
- `alert-hub::alert-hub:amc_assets` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_pms` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_parts` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_crew` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:total_assets` — value=30 — AI answer: __
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:logbook_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pm_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:last_failure` — value= — AI answer: __
- `asset-hub::asset-hub:rcm_edges` — value= — AI answer: __
- `pm-scheduler::pm-scheduler:overdue` — value=0 — AI answer: _The 'Overdue PMs' tile will show a non-zero value when there are preventive maintenance tasks past their due date. It re_
- `pm-scheduler::pm-scheduler:due_soon` — value=19 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:on_track` — value=12 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:hot_assets` — value=2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:healthy_assets` — value=1 — AI answer: __
- `predictive::predictive:earliest_forecast` — value=1.2d — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:risk_ranking` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:risk_heatmap` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:mtbf_trend` — value=Weekly Failure Count — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:out_of_stock` — value=0 — AI answer: __
- `inventory::inventory:low_stock` — value=3 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:pending_approval` — value=0 — AI answer: __
- `inventory::inventory:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:on_target` — value=5/5 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: __
- `skillmatrix::skillmatrix:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: __
- `hive::hive:adoption_health` — value=Healthy — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:open_issues` — value=21 — AI answer: __
- `hive::hive:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:xp_this_week` — value=+600 — AI answer: _The number reflects total community XP earned by the worker in the past 7 days, sourced from community_xp table joined t_
- `achievements::achievements:active_domains` — value=3/12 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:total_level` — value=71 — AI answer: __
- `achievements::achievements:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:composite_score` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:active_domains_stat` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:top_domain` — value= — AI answer: __
- `dayplanner::dayplanner:today_count` — value=0 — AI answer: __
- `dayplanner::dayplanner:week_count` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `dayplanner::dayplanner:overdue_count` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `dayplanner::dayplanner:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:active` — value=0 — AI answer: __
- `integrations::integrations:stale` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:disabled` — value=0 — AI answer: __
- `integrations::integrations:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:api_config` — value=Phase 5 · Intelligence API — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:sync_log` — value=Tier 2 · Scheduled API Sync — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:listings_in_view` — value=13 — AI answer: _the canonical source is listed in def#v_marketplace_sellers_truth_
- `marketplace::marketplace:my_listings` — value=1 — AI answer: __
- `marketplace::marketplace:current_tab` — value=Parts — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:listing_grid` — value=13 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `ph-intelligence::ph-intelligence:plants_in_network` — value=3 — AI answer: _The 'Plants in network' tile on the ph-intelligence.html page reflects the number of hives contributing anonymized data _
- `ph-intelligence::ph-intelligence:top_failure_cause` — value=Wear — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `ph-intelligence::ph-intelligence:report_freshness` — value=4d — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `ph-intelligence::ph-intelligence:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:project_list` — value=Project portfolio is climbing — a few things to handle2 past end_date. — AI answer: __
- `project-manager::project-manager:active_projects` — value=4 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:past_end_date` — value=2 — AI answer: __
- `project-manager::project-manager:on_hold_planning` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:project_cards` — value=SHD-2026-001 — AI answer: __
- `report-sender::report-sender:reports_selected` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:recipients` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:saved_contacts` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:top_risk_this_shift` — value=0 — AI answer: __
- `shift-brain::shift-brain:pms_due` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:carry_forward` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:detail_panel` — value=5 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
