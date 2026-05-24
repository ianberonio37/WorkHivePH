# RAG Flywheel — Turn 36 report
Generated: 2026-05-23T09:23:58.984469+00:00

## Walk metrics
- Tiles observed   : **83** (83 real / 0 dry)
- Pages walked     : 16 (achievements=7, alert-hub=8, analytics=5, asset-hub=8, dayplanner=4, hive=4, integrations=6, inventory=4, marketplace=5, ph-intelligence=4, pm-scheduler=4, predictive=7, project-manager=5, report-sender=4, shift-brain=4, skillmatrix=4)
- Routes used      : {'semantic': 62, 'n/a': 21}
- Avg latency      : 2306.5 ms
- Avg tokens       : 616.3

## Convergence metrics
- Grader pass rate    : **42.2%** (35/83)
- Checker pass rate   : **26.5%** (22/83)
- Citation coverage   : 41.0% (34/83 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **61**
- Tiles with zero citations           : **28**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_36_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:results_panel` — value= — AI answer: __
- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_pms` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_parts` — value= — AI answer: __
- `alert-hub::alert-hub:amc_crew` — value= — AI answer: _the canonical source is listed in def#v_alert_truth_
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: __
- `asset-hub::asset-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:logbook_count` — value= — AI answer: _the canonical source is listed in [def#v_logbook_truth]_
- `asset-hub::asset-hub:pm_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:last_failure` — value= — AI answer: __
- `asset-hub::asset-hub:rcm_edges` — value= — AI answer: __
- `pm-scheduler::pm-scheduler:due_soon` — value=18 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:on_track` — value=13 — AI answer: __
- `pm-scheduler::pm-scheduler:detail_panel` — value=4 rows — AI answer: __
- `predictive::predictive:hot_assets` — value=2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:healthy_assets` — value=1 — AI answer: _The 'Healthy assets' tile on the predictive.html page reflects the number of assets with no PM due soon, as defined by n_
- `predictive::predictive:earliest_forecast` — value=1.2d — AI answer: __
- `predictive::predictive:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:risk_heatmap` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:low_stock` — value=3 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:pending_approval` — value=0 — AI answer: __
- `inventory::inventory:detail_panel` — value=4 rows — AI answer: __
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: __
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: _The 'Total badges earned' tile reflects the count of workers who have met or exceeded their skill-count target, which is_
- `skillmatrix::skillmatrix:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: __
- `hive::hive:adoption_health` — value=Healthy — AI answer: __
- `hive::hive:open_issues` — value=21 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:active_domains` — value=3/12 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:total_level` — value=71 — AI answer: __
- `achievements::achievements:detail_panel` — value=4 rows — AI answer: __
- `achievements::achievements:composite_score` — value= — AI answer: _the canonical source is listed in [def#v_worker_skill_truth]_
- `achievements::achievements:active_domains_stat` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:top_domain` — value= — AI answer: _the canonical source is listed in [def#v_worker_skill_truth]_
- `dayplanner::dayplanner:week_count` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `dayplanner::dayplanner:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:stale` — value=0 — AI answer: __
- `integrations::integrations:disabled` — value=0 — AI answer: _The 'Disabled integrations' tile shows a non-zero value when there are connectors that have been turned off. It reads fr_
- `integrations::integrations:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:api_config` — value=Phase 5 · Intelligence API — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:sync_log` — value=Tier 2 · Scheduled API Sync — AI answer: __
- `marketplace::marketplace:my_listings` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:current_tab` — value=Parts — AI answer: __
- `marketplace::marketplace:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `ph-intelligence::ph-intelligence:plants_in_network` — value=3 — AI answer: _The number reflects the count of hives contributing anonymized data to the cross-network benchmarks, sourced from the ph_
- `ph-intelligence::ph-intelligence:top_failure_cause` — value=Wear — AI answer: __
- `ph-intelligence::ph-intelligence:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:active_projects` — value=4 — AI answer: _The number reflects active projects, but the provided chunks do not contain enough information to explain what this numb_
- `project-manager::project-manager:past_end_date` — value=2 — AI answer: _The 'Past end date' tile on the project-manager.html page reflects the last maintenance completion date for the assets i_
- `project-manager::project-manager:on_hold_planning` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:project_cards` — value=SHD-2026-001 — AI answer: _The number SHD-2026-001 reflects a project ID, which is a unique identifier for a project. The canonical source for proj_
- `report-sender::report-sender:recipients` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:saved_contacts` — value=0 — AI answer: __
- `report-sender::report-sender:detail_panel` — value=4 rows — AI answer: _The 4 rows in the 'Report sender detail' tile reflect the combination of selected reports, recipients, and saved contact_
- `shift-brain::shift-brain:pms_due` — value=0 — AI answer: __
- `shift-brain::shift-brain:carry_forward` — value=0 — AI answer: _The 'Carry-forward' tile shows a non-zero value when there are logbook items from the previous shift that are still open_
- `shift-brain::shift-brain:detail_panel` — value=5 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
