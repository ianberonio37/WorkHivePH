# RAG Flywheel — Turn 29 report
Generated: 2026-05-22T20:20:35.428459+00:00

## Walk metrics
- Tiles observed   : **51** (51 real / 0 dry)
- Pages walked     : 16 (achievements=3, alert-hub=3, analytics=3, asset-hub=3, dayplanner=3, hive=3, integrations=4, inventory=3, marketplace=3, ph-intelligence=3, pm-scheduler=3, predictive=5, project-manager=3, report-sender=3, shift-brain=3, skillmatrix=3)
- Routes used      : {'semantic': 35, 'n/a': 16}
- Avg latency      : 4767.3 ms
- Avg tokens       : 718.5

## Convergence metrics
- Grader pass rate    : **49.0%** (25/51)
- Checker pass rate   : **47.1%** (24/51)
- Citation coverage   : 49.0% (25/51 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **27**
- Tiles with zero citations           : **10**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_29_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `alert-hub::alert-hub:high_severity_alerts` — value=37 — AI answer: __
- `asset-hub::asset-hub:total_assets` — value=30 — AI answer: __
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: __
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: __
- `predictive::predictive:healthy_assets` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:earliest_forecast` — value=1.2d — AI answer: __
- `inventory::inventory:low_stock` — value=3 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:adoption_health` — value=Healthy — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:open_issues` — value=21 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:active_domains` — value=3/12 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:listings_in_view` — value=13 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:my_listings` — value=1 — AI answer: _The "My listings" tile shows the count of listings that belong to the current seller and are marked as published (or act_
- `ph-intelligence::ph-intelligence:plants_in_network` — value=3 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `ph-intelligence::ph-intelligence:top_failure_cause` — value=Wear — AI answer: __
- `ph-intelligence::ph-intelligence:report_freshness` — value=3d — AI answer: __
- `project-manager::project-manager:active_projects` — value=4 — AI answer: __
- `project-manager::project-manager:past_end_date` — value=2 — AI answer: __
- `project-manager::project-manager:on_hold_planning` — value=0 — AI answer: __
- `report-sender::report-sender:reports_selected` — value=0 — AI answer: __
- `report-sender::report-sender:recipients` — value=0 — AI answer: __
- `report-sender::report-sender:saved_contacts` — value=0 — AI answer: __
- `shift-brain::shift-brain:top_risk_this_shift` — value=0 — AI answer: __
- `shift-brain::shift-brain:pms_due` — value=0 — AI answer: __
- `shift-brain::shift-brain:carry_forward` — value=0 — AI answer: __
