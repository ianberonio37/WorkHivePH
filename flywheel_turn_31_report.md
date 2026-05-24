# RAG Flywheel — Turn 31 report
Generated: 2026-05-22T20:31:48.051572+00:00

## Walk metrics
- Tiles observed   : **83** (83 real / 0 dry)
- Pages walked     : 16 (achievements=7, alert-hub=8, analytics=5, asset-hub=8, dayplanner=4, hive=4, integrations=6, inventory=4, marketplace=5, ph-intelligence=4, pm-scheduler=4, predictive=7, project-manager=5, report-sender=4, shift-brain=4, skillmatrix=4)
- Routes used      : {'n/a': 83}
- Avg latency      : 0.0 ms
- Avg tokens       : 0.0

## Convergence metrics
- Grader pass rate    : **0.0%** (0/83)
- Checker pass rate   : **0.0%** (0/83)
- Citation coverage   : 0.0% (0/83 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **83**
- Tiles with zero citations           : **0**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_31_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:oee` — value=— — AI answer: __
- `analytics::analytics:mtbf` — value=— — AI answer: __
- `analytics::analytics:pm_compliance` — value=— — AI answer: __
- `analytics::analytics:detail_panel` — value=4 rows — AI answer: __
- `analytics::analytics:results_panel` — value= — AI answer: __
- `alert-hub::alert-hub:high_severity_alerts` — value=37 — AI answer: __
- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: __
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: __
- `alert-hub::alert-hub:detail_panel` — value=4 rows — AI answer: __
- `alert-hub::alert-hub:amc_assets` — value= — AI answer: __
- `alert-hub::alert-hub:amc_pms` — value= — AI answer: __
- `alert-hub::alert-hub:amc_parts` — value= — AI answer: __
- `alert-hub::alert-hub:amc_crew` — value= — AI answer: __
- `asset-hub::asset-hub:total_assets` — value=30 — AI answer: __
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: __
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: __
- `asset-hub::asset-hub:detail_panel` — value=4 rows — AI answer: __
- `asset-hub::asset-hub:logbook_count` — value= — AI answer: __
- `asset-hub::asset-hub:pm_count` — value= — AI answer: __
- `asset-hub::asset-hub:last_failure` — value= — AI answer: __
- `asset-hub::asset-hub:rcm_edges` — value= — AI answer: __
- `pm-scheduler::pm-scheduler:overdue` — value=0 — AI answer: __
- `pm-scheduler::pm-scheduler:due_soon` — value=15 — AI answer: __
- `pm-scheduler::pm-scheduler:on_track` — value=16 — AI answer: __
- `pm-scheduler::pm-scheduler:detail_panel` — value=4 rows — AI answer: __
- `predictive::predictive:hot_assets` — value=2 — AI answer: __
- `predictive::predictive:healthy_assets` — value=1 — AI answer: __
- `predictive::predictive:earliest_forecast` — value=1.2d — AI answer: __
- `predictive::predictive:detail_panel` — value=4 rows — AI answer: __
- `predictive::predictive:risk_ranking` — value=4 rows — AI answer: __
- `predictive::predictive:risk_heatmap` — value= — AI answer: __
- `predictive::predictive:mtbf_trend` — value=Weekly Failure Count — AI answer: __
- `inventory::inventory:out_of_stock` — value=0 — AI answer: __
- `inventory::inventory:low_stock` — value=3 — AI answer: __
- `inventory::inventory:pending_approval` — value=0 — AI answer: __
- `inventory::inventory:detail_panel` — value=4 rows — AI answer: __
- `skillmatrix::skillmatrix:on_target` — value=5/5 — AI answer: __
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: __
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: __
- `skillmatrix::skillmatrix:detail_panel` — value=4 rows — AI answer: __
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: __
- `hive::hive:adoption_health` — value=Healthy — AI answer: __
- `hive::hive:open_issues` — value=21 — AI answer: __
- `hive::hive:detail_panel` — value=4 rows — AI answer: __
- `achievements::achievements:xp_this_week` — value=+600 — AI answer: __
- `achievements::achievements:active_domains` — value=3/12 — AI answer: __
- `achievements::achievements:total_level` — value=71 — AI answer: __
- `achievements::achievements:detail_panel` — value=4 rows — AI answer: __
- `achievements::achievements:composite_score` — value= — AI answer: __
- `achievements::achievements:active_domains_stat` — value= — AI answer: __
- `achievements::achievements:top_domain` — value= — AI answer: __
- `dayplanner::dayplanner:today_count` — value=0 — AI answer: __
- `dayplanner::dayplanner:week_count` — value=6 — AI answer: __
- `dayplanner::dayplanner:overdue_count` — value=6 — AI answer: __
- `dayplanner::dayplanner:detail_panel` — value=4 rows — AI answer: __
- `integrations::integrations:active` — value=0 — AI answer: __
- `integrations::integrations:stale` — value=0 — AI answer: __
- `integrations::integrations:disabled` — value=0 — AI answer: __
- `integrations::integrations:detail_panel` — value=4 rows — AI answer: __
- `integrations::integrations:api_config` — value=Phase 5 · Intelligence API — AI answer: __
- `integrations::integrations:sync_log` — value=Tier 2 · Scheduled API Sync — AI answer: __
- `marketplace::marketplace:listings_in_view` — value=13 — AI answer: __
- `marketplace::marketplace:my_listings` — value=1 — AI answer: __
- `marketplace::marketplace:current_tab` — value=Parts — AI answer: __
- `marketplace::marketplace:detail_panel` — value=4 rows — AI answer: __
- `marketplace::marketplace:listing_grid` — value=13 rows — AI answer: __
- `ph-intelligence::ph-intelligence:plants_in_network` — value=3 — AI answer: __
- `ph-intelligence::ph-intelligence:top_failure_cause` — value=Wear — AI answer: __
- `ph-intelligence::ph-intelligence:report_freshness` — value=3d — AI answer: __
- `ph-intelligence::ph-intelligence:detail_panel` — value=4 rows — AI answer: __
- `project-manager::project-manager:project_list` — value=Project portfolio is climbing — a few things to handle2 past end_date. — AI answer: __
- `project-manager::project-manager:active_projects` — value=4 — AI answer: __
- `project-manager::project-manager:past_end_date` — value=2 — AI answer: __
- `project-manager::project-manager:on_hold_planning` — value=0 — AI answer: __
- `project-manager::project-manager:project_cards` — value=SHD-2026-001 — AI answer: __
- `report-sender::report-sender:reports_selected` — value=0 — AI answer: __
- `report-sender::report-sender:recipients` — value=0 — AI answer: __
- `report-sender::report-sender:saved_contacts` — value=0 — AI answer: __
- `report-sender::report-sender:detail_panel` — value=4 rows — AI answer: __
- `shift-brain::shift-brain:top_risk_this_shift` — value=0 — AI answer: __
- `shift-brain::shift-brain:pms_due` — value=0 — AI answer: __
- `shift-brain::shift-brain:carry_forward` — value=0 — AI answer: __
- `shift-brain::shift-brain:detail_panel` — value=5 rows — AI answer: __
