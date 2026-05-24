# RAG Flywheel — Turn 49 report
Generated: 2026-05-23T22:15:14.745151+00:00

## Walk metrics
- Tiles observed   : **104** (104 real / 0 dry)
- Pages walked     : 16 (achievements=7, alert-hub=16, analytics=10, asset-hub=16, dayplanner=4, hive=4, integrations=6, inventory=4, marketplace=5, ph-intelligence=4, pm-scheduler=4, predictive=7, project-manager=5, report-sender=4, shift-brain=4, skillmatrix=4)
- Routes used      : {'semantic': 101, 'n/a': 3}
- Avg latency      : 4727.0 ms
- Avg tokens       : 1102.0

## Convergence metrics
- Grader pass rate    : **83.7%** (87/104)
- Checker pass rate   : **80.8%** (84/104)
- Citation coverage   : 77.9% (81/104 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **20**
- Tiles with zero citations           : **20**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_49_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:detail_panel` — value=4 rows — AI answer: _The source of the number of rows shown on the 'Analytics detail breakdown' tile on the analytics.html page is not explic_
- `alert-hub::alert-hub:amc_crew` — value= — AI answer: __
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: __
- `asset-hub::asset-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:oee` — value=— — AI answer: _The canonical source view for the 'OEE (avg, partial)' KPI is listed in v_OEE_truth._
- `skillmatrix::skillmatrix:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:adoption_health` — value=Healthy — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:active_domains` — value=3/12 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `dayplanner::dayplanner:week_count` — value=6 — AI answer: __
- `integrations::integrations:api_config` — value=Phase 5 · Intelligence API — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:sync_log` — value=Tier 2 · Scheduled API Sync — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:my_listings` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `ph-intelligence::ph-intelligence:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:project_list` — value=Project portfolio is climbing — a few things to handle2 past end_date. — AI answer: _The 'Project portfolio is climbing — a few things to handle past end_date' message reflects project progress tracking fr_
- `project-manager::project-manager:active_projects` — value=4 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:project_cards` — value=SHD-2026-001 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `report-sender::report-sender:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:detail_panel` — value=5 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
