# RAG Flywheel — Turn 38 report
Generated: 2026-05-23T09:54:29.323514+00:00

## Walk metrics
- Tiles observed   : **83** (83 real / 0 dry)
- Pages walked     : 16 (achievements=7, alert-hub=8, analytics=5, asset-hub=8, dayplanner=4, hive=4, integrations=6, inventory=4, marketplace=5, ph-intelligence=4, pm-scheduler=4, predictive=7, project-manager=5, report-sender=4, shift-brain=4, skillmatrix=4)
- Routes used      : {'semantic': 63, 'n/a': 20}
- Avg latency      : 2179.8 ms
- Avg tokens       : 619.0

## Convergence metrics
- Grader pass rate    : **41.0%** (34/83)
- Checker pass rate   : **31.3%** (26/83)
- Citation coverage   : 41.0% (34/83 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **57**
- Tiles with zero citations           : **29**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_38_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: _The AMC daily brief tile on the alert-hub.html page would show a non-zero value when the Autonomous Maintenance Crew bri_
- `alert-hub::alert-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_assets` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_pms` — value= — AI answer: _The canonical source view for the 'AMC PMs flagged' KPI is v_amc_truth._
- `alert-hub::alert-hub:amc_parts` — value= — AI answer: __
- `alert-hub::alert-hub:amc_crew` — value= — AI answer: _The 'AMC crew alerts' KPI on the alert-hub.html page measures AMC crew briefing status [def#v_amc_truth]. The canonical _
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: __
- `asset-hub::asset-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pm_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:last_failure` — value= — AI answer: __
- `asset-hub::asset-hub:rcm_edges` — value= — AI answer: __
- `pm-scheduler::pm-scheduler:due_soon` — value=18 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:on_track` — value=13 — AI answer: __
- `pm-scheduler::pm-scheduler:detail_panel` — value=4 rows — AI answer: __
- `predictive::predictive:hot_assets` — value=2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:earliest_forecast` — value=1.2d — AI answer: __
- `predictive::predictive:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:risk_ranking` — value=4 rows — AI answer: _The number of rows in the 'Risk ranking table' tile on the predictive.html page reflects the number of assets with a ris_
- `predictive::predictive:risk_heatmap` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:mtbf_trend` — value=Weekly Failure Count — AI answer: __
- `inventory::inventory:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:detail_panel` — value=4 rows — AI answer: __
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: __
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: _The 'Hive maturity stair' tile showing Stair 2 cannot be explained using the provided chunks. None of the available cano_
- `hive::hive:adoption_health` — value=Healthy — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:open_issues` — value=21 — AI answer: __
- `hive::hive:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:active_domains` — value=3/12 — AI answer: __
- `achievements::achievements:total_level` — value=71 — AI answer: _The 'Total level' tile on the achievements.html page reflects the total level of all workers across all hives, which is _
- `achievements::achievements:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:composite_score` — value= — AI answer: __
- `achievements::achievements:active_domains_stat` — value= — AI answer: __
- `achievements::achievements:top_domain` — value= — AI answer: __
- `dayplanner::dayplanner:week_count` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `dayplanner::dayplanner:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:stale` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:disabled` — value=0 — AI answer: _The Disabled integrations KPI on integrations.html shows a non-zero value when at least one connector is turned off. It _
- `integrations::integrations:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:api_config` — value=Phase 5 · Intelligence API — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:sync_log` — value=Tier 2 · Scheduled API Sync — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:my_listings` — value=1 — AI answer: __
- `marketplace::marketplace:current_tab` — value=Parts — AI answer: _The 'Current tab' tile on the marketplace.html page showing Parts reflects the number of parts that are low in stock, wh_
- `marketplace::marketplace:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:listing_grid` — value=13 rows — AI answer: __
- `ph-intelligence::ph-intelligence:top_failure_cause` — value=Wear — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `ph-intelligence::ph-intelligence:report_freshness` — value=3d — AI answer: __
- `ph-intelligence::ph-intelligence:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:past_end_date` — value=2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:project_cards` — value=SHD-2026-001 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:recipients` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:pms_due` — value=0 — AI answer: __
- `shift-brain::shift-brain:carry_forward` — value=0 — AI answer: __
- `shift-brain::shift-brain:detail_panel` — value=5 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
