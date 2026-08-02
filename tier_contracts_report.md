# Tier Contract Audit (Layer -1.5 four-tier registry health)

Surveys the four canonical registries — Fuel / Engine / Brain / Glue —
and reports registered vs candidate count per tier. Chain integrity
failures (registry entries pointing at non-existent IDs) fail the gate.

| Tier | Registry file | Registered | Discovered | Pending |
|---|---|---:|---:|---:|
| F (Fuel) | `canonical/capture_contracts.json` | 494 | 259 | 40 |
| E (Engine) | `canonical/formula_contracts.json` | 24 | 22 | 19 |
| B (Brain) | `canonical/agent_contracts.json` | 7 | 99 | 14 |
| Glue (lineage edges) | `canonical/lineage_edges.json` | 17 | — | — |

## Tier F (Fuel) — pending registrations (40)

- `cl-text`
- `f-loto`
- `f-permit-ref`
- `file-any`
- `file-photo`
- `filter-route`
- `filter-window`
- `group-filter`
- `ideal_cycle_time_seconds`
- `jd-input`
- `post-part-number`
- `post-source-item-id`
- `promote-dedupe`
- `rm-current-title`
- `status-filter`
- `svc-hail-address`
- `svc-hail-item`
- `svc-hail-urgency`
- `svc-pay-amt-`
- `svc-pay-method-`
- `svc-pay-ref-`
- `svc-pay-why-`
- `svc-prate-comment-`
- `svc-q-`
- `svc-quote-address`
- `svc-quote-budget`
- `svc-quote-scope`
- `svc-rate-comment-`
- `svc-reg-area`
- `svc-reg-contact`
- `svc-reg-name`
- `svc-topup-amt-`
- `svc-topup-ref-`
- `svc-vcode-`
- `vm-code`
- `vm-kind`
- `vm-maxuses`
- `vm-segment`
- `vm-value`
- `window`

## Tier E (Engine) — pending registrations (19)

- `get_adoption_risk_current`
- `get_community_reputation`
- `get_community_reputation_by_auth`
- `get_downtime_pareto`
- `get_failure_frequency`
- `get_hive_board_dashboard`
- `get_hive_dashboard`
- `get_hive_readiness_current`
- `get_hive_trade_peers`
- `get_marketplace_parts_for_my_assets`
- `get_marketplace_price_comps`
- `get_marketplace_seller_public`
- `get_marketplace_trust_badges`
- `get_pm_compliance_smrp`
- `get_pm_ontime_delivery`
- `get_project_budget`
- `get_repeat_failures`
- `get_saved_search_matches`
- `get_seller_community_reputation`

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
