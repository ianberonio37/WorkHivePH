# RAG Flywheel — Turn 26 report
Generated: 2026-05-22T07:44:04.836919+00:00

## Walk metrics
- Tiles observed   : **48** (48 real / 0 dry)
- Pages walked     : 16 (achievements=3, alert-hub=3, analytics=3, asset-hub=3, dayplanner=3, hive=3, integrations=3, inventory=3, marketplace=3, ph-intelligence=3, pm-scheduler=3, predictive=3, project-manager=3, report-sender=3, shift-brain=3, skillmatrix=3)
- Routes used      : {'semantic': 38, 'cold_archive': 2, 'n/a': 8}
- Avg latency      : 8742.5 ms
- Avg tokens       : 791.9

## Convergence metrics
- Grader pass rate    : **60.4%** (29/48)
- Checker pass rate   : **52.1%** (25/48)
- Citation coverage   : 54.2% (26/48 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **11**
- Tiles with checker FAIL (need work) : **23**
- Tiles with zero citations           : **14**

## Auto-actions taken
- canonical_sources INSERTed : **1**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_26_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:total_assets` — value=30 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: __
- `predictive::predictive:hot_assets` — value=2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:total_badges` — value=19 — AI answer: _Ang 'Total badges earned' na 19 ay nagmumula sa 'badge_count' sa [def#v_worker_skill_truth] na canonical view, na nagtat_
- `hive::hive:maturity_stair` — value=Stair 2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `hive::hive:open_issues` — value=21 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:xp_this_week` — value=+600 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `dayplanner::dayplanner:week_count` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `dayplanner::dayplanner:overdue_count` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `integrations::integrations:disabled` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `ph-intelligence::ph-intelligence:top_failure_cause` — value=Wear — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `ph-intelligence::ph-intelligence:report_freshness` — value=2d — AI answer: _The 'Report freshness' tile on the ph-intelligence.html page shows how recent the network benchmark report is, in days, _
- `project-manager::project-manager:active_projects` — value=4 — AI answer: _Ang 4 na ipinapakita sa 'Active projects' tile ay tumutukoy sa bilang ng mga proyekto sa 'projects' table na may status _
- `project-manager::project-manager:past_end_date` — value=2 — AI answer: __
- `project-manager::project-manager:on_hold_planning` — value=0 — AI answer: __
- `report-sender::report-sender:reports_selected` — value=0 — AI answer: __
- `report-sender::report-sender:recipients` — value=0 — AI answer: __
- `report-sender::report-sender:saved_contacts` — value=0 — AI answer: __
- `shift-brain::shift-brain:top_risk_this_shift` — value=0 — AI answer: __
- `shift-brain::shift-brain:pms_due` — value=0 — AI answer: __
- `shift-brain::shift-brain:carry_forward` — value=0 — AI answer: __

## Tiles missing canonical anchor (auto-seeded above if --commit)

- `rag_tile:pm-scheduler:on_track` — inferred source: `logbook`
- `rag_tile:achievements:xp_this_week` — inferred source: `None`
- `rag_tile:dayplanner:overdue_count` — inferred source: `None`
- `rag_tile:integrations:stale` — inferred source: `None`
- `rag_tile:integrations:disabled` — inferred source: `None`
- `rag_tile:ph-intelligence:plants_in_network` — inferred source: `None`
- `rag_tile:ph-intelligence:report_freshness` — inferred source: `None`
- `rag_tile:project-manager:on_hold_planning` — inferred source: `None`
- `rag_tile:report-sender:reports_selected` — inferred source: `None`
- `rag_tile:report-sender:recipients` — inferred source: `None`
- `rag_tile:report-sender:saved_contacts` — inferred source: `None`
