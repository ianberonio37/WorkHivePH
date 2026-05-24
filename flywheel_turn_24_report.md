# RAG Flywheel — Turn 24 report
Generated: 2026-05-22T07:49:26.262366+00:00

## Walk metrics
- Tiles observed   : **48** (48 real / 0 dry)
- Pages walked     : 16 (achievements=3, alert-hub=3, analytics=3, asset-hub=3, dayplanner=3, hive=3, integrations=3, inventory=3, marketplace=3, ph-intelligence=3, pm-scheduler=3, predictive=3, project-manager=3, report-sender=3, shift-brain=3, skillmatrix=3)
- Routes used      : {'semantic': 46, 'cold_archive': 1, 'simple_recency': 1}
- Avg latency      : 2991.2 ms
- Avg tokens       : 1093.6

## Convergence metrics
- Grader pass rate    : **95.8%** (46/48)
- Checker pass rate   : **93.8%** (45/48)
- Citation coverage   : 95.8% (46/48 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **10**
- Tiles with checker FAIL (need work) : **3**
- Tiles with zero citations           : **2**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **0**
- L2 review queue            : `.tmp/flywheel_turn_24_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:oee` — value=— — AI answer: _The 'OEE (avg, partial)' KPI on the analytics.html page sources from view v_OEE_truth. However, the provided chunks do n_
- `achievements::achievements:xp_this_week` — value=+600 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `project-manager::project-manager:past_end_date` — value=2 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._

## Tiles missing canonical anchor (auto-seeded above if --commit)

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
