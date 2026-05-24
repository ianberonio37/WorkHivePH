# RAG Flywheel — Turn 28 report
Generated: 2026-05-22T20:08:03.781860+00:00

## Walk metrics
- Tiles observed   : **48** (48 real / 0 dry)
- Pages walked     : 16 (achievements=3, alert-hub=3, analytics=3, asset-hub=3, dayplanner=3, hive=3, integrations=3, inventory=3, marketplace=3, ph-intelligence=3, pm-scheduler=3, predictive=3, project-manager=3, report-sender=3, shift-brain=3, skillmatrix=3)
- Routes used      : {'semantic': 47, 'cold_archive': 1}
- Avg latency      : 3781.1 ms
- Avg tokens       : 1004.3

## Convergence metrics
- Grader pass rate    : **85.4%** (41/48)
- Checker pass rate   : **85.4%** (41/48)
- Citation coverage   : 85.4% (41/48 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **10**
- Tiles with checker FAIL (need work) : **7**
- Tiles with zero citations           : **7**

## Auto-actions taken
- canonical_sources INSERTed : **1**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_28_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `pm-scheduler::pm-scheduler:on_track` — value=16 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `inventory::inventory:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `skillmatrix::skillmatrix:quizzes_available` — value=1 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `achievements::achievements:xp_this_week` — value=+600 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `ph-intelligence::ph-intelligence:top_failure_cause` — value=Wear — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:past_end_date` — value=2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `shift-brain::shift-brain:pms_due` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._

## Tiles missing canonical anchor (auto-seeded above if --commit)

- `rag_tile:achievements:xp_this_week` — inferred source: `None`
- `rag_tile:dayplanner:overdue_count` — inferred source: `logbook`
- `rag_tile:integrations:stale` — inferred source: `None`
- `rag_tile:integrations:disabled` — inferred source: `None`
- `rag_tile:ph-intelligence:plants_in_network` — inferred source: `None`
- `rag_tile:ph-intelligence:report_freshness` — inferred source: `None`
- `rag_tile:project-manager:on_hold_planning` — inferred source: `None`
- `rag_tile:report-sender:reports_selected` — inferred source: `None`
- `rag_tile:report-sender:recipients` — inferred source: `None`
- `rag_tile:report-sender:saved_contacts` — inferred source: `None`
