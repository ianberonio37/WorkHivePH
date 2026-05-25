# RAG Flywheel — Turn 68 report
Generated: 2026-05-24T09:06:31.328532+00:00

## Walk metrics
- Tiles observed   : **62** (62 real / 0 dry)
- Pages walked     : 11 (achievements=7, alert-hub=8, analytics=5, asset-hub=8, integrations=6, inventory=4, marketplace=5, pm-scheduler=4, predictive=7, report-sender=4, skillmatrix=4)
- Routes used      : {'semantic': 38, 'n/a': 24}
- Avg latency      : 4342.7 ms
- Avg tokens       : 465.8

## Convergence metrics
- Grader pass rate    : **30.6%** (19/62)
- Checker pass rate   : **21.0%** (13/62)
- Citation coverage   : 30.6% (19/62 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **0**
- Tiles with checker FAIL (need work) : **49**
- Tiles with zero citations           : **19**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_68_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `alert-hub::alert-hub:high_severity_alerts` — value=37 — AI answer: __
- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: __
- `alert-hub::alert-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_assets` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_pms` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_parts` — value= — AI answer: __
- `alert-hub::alert-hub:amc_crew` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:total_assets` — value=30 — AI answer: __
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: __
- `asset-hub::asset-hub:detail_panel` — value=4 rows — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:logbook_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pm_count` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:last_failure` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:rcm_edges` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:due_soon` — value=19 — AI answer: _The number 19 on the pm-scheduler.html page reflects the count of preventive maintenance tasks coming due in the next 14_
- `pm-scheduler::pm-scheduler:on_track` — value=12 — AI answer: __
- `pm-scheduler::pm-scheduler:detail_panel` — value=4 rows — AI answer: __
- `predictive::predictive:hot_assets` — value=2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:healthy_assets` — value=1 — AI answer: _The 'Healthy assets' tile on the predictive.html page shows 1, which reflects the number of assets that are currently he_
- `predictive::predictive:earliest_forecast` — value=1.2d — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:detail_panel` — value=4 rows — AI answer: __
- `predictive::predictive:risk_ranking` — value=4 rows — AI answer: _The 'Risk ranking table' tile on the predictive.html page shows 4 rows, reflecting the number of assets with the highest_
- `predictive::predictive:risk_heatmap` — value= — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `predictive::predictive:mtbf_trend` — value=Weekly Failure Count — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:out_of_stock` — value=0 — AI answer: __
- `inventory::inventory:low_stock` — value=3 — AI answer: _The 'Low stock' tile on the inventory.html page reflects the number of parts that are low in stock, not out of stock. Th_
- `inventory::inventory:pending_approval` — value=0 — AI answer: __
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: __
- `skillmatrix::skillmatrix:detail_panel` — value=4 rows — AI answer: __
- `achievements::achievements:xp_this_week` — value=+600 — AI answer: __
- `achievements::achievements:active_domains` — value=3/12 — AI answer: __
- `achievements::achievements:total_level` — value=71 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:detail_panel` — value=4 rows — AI answer: __
- `achievements::achievements:composite_score` — value= — AI answer: __
- `achievements::achievements:top_domain` — value= — AI answer: __
- `integrations::integrations:disabled` — value=0 — AI answer: _The 'Disabled integrations' tile on the integrations.html page would show a non-zero value when connectors are turned of_
- `integrations::integrations:detail_panel` — value=4 rows — AI answer: __
- `integrations::integrations:api_config` — value=Phase 5 · Intelligence API — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:sync_log` — value=Tier 2 · Scheduled API Sync — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `marketplace::marketplace:listings_in_view` — value=13 — AI answer: __
- `marketplace::marketplace:my_listings` — value=1 — AI answer: __
- `marketplace::marketplace:current_tab` — value=Parts — AI answer: _The 'Current tab' tile on the marketplace.html page showing Parts reflects the number of parts currently out of stock or_
- `marketplace::marketplace:listing_grid` — value=13 rows — AI answer: __
- `report-sender::report-sender:recipients` — value=0 — AI answer: __
- `report-sender::report-sender:saved_contacts` — value=0 — AI answer: __
- `report-sender::report-sender:detail_panel` — value=4 rows — AI answer: __
