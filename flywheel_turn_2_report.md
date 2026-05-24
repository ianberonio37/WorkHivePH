# RAG Flywheel — Turn 2 report
Generated: 2026-05-21T11:12:57.548266+00:00

## Walk metrics
- Tiles observed   : **12** (12 real / 0 dry)
- Pages walked     : 4 (alert-hub=3, analytics=3, asset-hub=3, pm-scheduler=3)
- Routes used      : {'semantic': 12}
- Avg latency      : 4848.5 ms
- Avg tokens       : 1078.0

## Convergence metrics
- Grader pass rate    : **0.0%** (0/12)
- Checker pass rate   : **0.0%** (0/12)
- Citation coverage   : 0.0% (0/12 tiles had ≥1 citation)

## Gaps found
- Tiles missing canonical anchor      : **12**
- Tiles with checker FAIL (need work) : **12**
- Tiles with zero citations           : **12**

## Auto-actions taken
- canonical_sources INSERTed : **0**
- New L0 tile locks added    : **12**
- L2 review queue            : `.tmp/flywheel_turn_2_l2_review.md` (manual review per locked decision)

## Tiles needing work (checker failed)

- `analytics::analytics:oee` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:mtbf` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `analytics::analytics:pm_compliance` — value=— — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:high_severity_alerts` — value=36 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:anomaly_signals` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `alert-hub::alert-hub:amc_daily_brief` — value=None today — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:total_assets` — value=30 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:critical_assets` — value=6 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `asset-hub::asset-hub:pending_approval` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:overdue` — value=0 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:due_soon` — value=15 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._
- `pm-scheduler::pm-scheduler:on_track` — value=15 — AI answer: _I don't have enough recent records to answer that. Try rephrasing or asking about a specific asset / date._

## Tiles missing canonical anchor (auto-seeded above if --commit)

- `rag_tile:analytics:oee` — inferred source: `None`
- `rag_tile:analytics:mtbf` — inferred source: `None`
- `rag_tile:analytics:pm_compliance` — inferred source: `None`
- `rag_tile:alert-hub:high_severity_alerts` — inferred source: `None`
- `rag_tile:alert-hub:anomaly_signals` — inferred source: `None`
- `rag_tile:alert-hub:amc_daily_brief` — inferred source: `None`
- `rag_tile:asset-hub:total_assets` — inferred source: `None`
- `rag_tile:asset-hub:critical_assets` — inferred source: `None`
- `rag_tile:asset-hub:pending_approval` — inferred source: `None`
- `rag_tile:pm-scheduler:overdue` — inferred source: `None`
- `rag_tile:pm-scheduler:due_soon` — inferred source: `None`
- `rag_tile:pm-scheduler:on_track` — inferred source: `None`
