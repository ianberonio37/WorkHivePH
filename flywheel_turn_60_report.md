# RAG Flywheel — Turn 60 report
Generated: 2026-05-24T05:05:43.195692+00:00

## Walk metrics
- Tiles observed   : **83** (83 real / 0 dry)
- Pages walked     : 16 (achievements=7, alert-hub=8, analytics=5, asset-hub=8, dayplanner=4, hive=4, integrations=6, inventory=4, marketplace=5, ph-intelligence=4, pm-scheduler=4, predictive=7, project-manager=5, report-sender=4, shift-brain=4, skillmatrix=4)
- Routes used      : {'semantic': 66, 'n/a': 16, 'simple_recency': 1}
- Avg latency      : 2604.9 ms
- Avg tokens       : 531.9

## Convergence metrics
- Grader pass rate    : **28.9%** (24/83)
- Checker pass rate   : **24.1%** (20/83)
- Citation coverage   : 28.9% (24/83 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **63**
- Tiles with zero citations           : **43**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_60_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:mtbf` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:pm_compliance` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:detail_panel` — value=4 rows — AI answer: __
- `analytics::analytics:results_panel` — value= — AI answer: __
- `alert-hub::alert-hub:high_severity_alerts` — value=37 — AI answer: __
- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: __
- `alert-hub::alert-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_assets` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_pms` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_parts` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_crew` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: __
- `asset-hub::asset-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:logbook_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pm_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:last_failure` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:rcm_edges` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:overdue` — value=0 — AI answer: __
- `pm-scheduler::pm-scheduler:due_soon` — value=19 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:on_track` — value=12 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:hot_assets` — value=2 — AI answer: _The 'Hot assets' tile on the predictive.html page shows the number of assets that are due for PM soon, based on the v_pm_
- `predictive::predictive:healthy_assets` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:earliest_forecast` — value=1.2d — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:detail_panel` — value=4 rows — AI answer: __
- `predictive::predictive:risk_ranking` — value=4 rows — AI answer: __
- `predictive::predictive:risk_heatmap` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:mtbf_trend` — value=Weekly Failure Count — AI answer: __
- `inventory::inventory:out_of_stock` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:low_stock` — value=3 — AI answer: __
- `inventory::inventory:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:on_target` — value=5/5 — AI answer: _The number reflects workers who have met or exceeded their skill-count target, sourced from v_worker_skill_truth, the ca_
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:adoption_health` — value=Healthy — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:open_issues` — value=21 — AI answer: __
- `hive::hive:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:xp_this_week` — value=+600 — AI answer: __
- `achievements::achievements:active_domains` — value=3/12 — AI answer: __
- `achievements::achievements:total_level` — value=71 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:composite_score` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:active_domains_stat` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:top_domain` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `dayplanner::dayplanner:today_count` — value=0 — AI answer: _The 'Tasks today' tile on the dayplanner.html page shows a non-zero value when there are schedule_items due today for th_
- `dayplanner::dayplanner:week_count` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `dayplanner::dayplanner:overdue_count` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `dayplanner::dayplanner:detail_panel` — value=4 rows — AI answer: __
- `integrations::integrations:active` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:stale` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:disabled` — value=0 — AI answer: __
- `integrations::integrations:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:api_config` — value=Phase 5 · Intelligence API — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:sync_log` — value=Tier 2 · Scheduled API Sync — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:listings_in_view` — value=13 — AI answer: __
- `project-manager::project-manager:project_cards` — value=SHD-2026-001 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:pms_due` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:detail_panel` — value=5 rows — AI answer: _The 'Shift brain detail' tile on the shift-brain.html page shows 5 rows, reflecting the top 5 risk assets for the curren_
