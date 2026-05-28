# Tier Contract Audit (Layer -1.5 four-tier registry health)

Surveys the four canonical registries — Fuel / Engine / Brain / Glue —
and reports registered vs candidate count per tier. Chain integrity
failures (registry entries pointing at non-existent IDs) fail the gate.

| Tier | Registry file | Registered | Discovered | Pending |
|---|---|---:|---:|---:|
| F (Fuel) | `canonical/capture_contracts.json` | 494 | 498 | 6 |
| E (Engine) | `canonical/formula_contracts.json` | 22 | 8 | 5 |
| B (Brain) | `canonical/agent_contracts.json` | 7 | 76 | 14 |
| Glue (lineage edges) | `canonical/lineage_edges.json` | 17 | — | — |

## Tier F (Fuel) — pending registrations (6)

- `filter-route`
- `filter-window`
- `group-filter`
- `ideal_cycle_time_seconds`
- `status-filter`
- `window`

## Tier E (Engine) — pending registrations (5)

- `get_adoption_risk_current`
- `get_downtime_pareto`
- `get_failure_frequency`
- `get_hive_readiness_current`
- `get_repeat_failures`

## Tier B (Brain) — pending registrations (14)

- `agent-memory-store`
- `agentic-rag-loop`
- `ai-orchestrator`
- `amc-orchestrator`
- `asset-brain-query`
- `cold-archive-query`
- `engineering-calc-agent`
- `failure-signature-scan`
- `fmea-populator`
- `project-orchestrator`
- `scheduled-agents`
- `shift-planner-orchestrator`
- `temporal-rag-orchestrator`
- `voice-journal-agent`
