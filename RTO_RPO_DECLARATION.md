# WorkHive RTO / RPO Declaration

**Status:** v0.1 (P1 roadmap 2026-05-26)
**Owner:** Ian + Claude
**Required by:** any enterprise contract, ISO 27001 / SOC 2 audit

RTO = Recovery Time Objective (how long until service is restored)
RPO = Recovery Point Objective (how much data we accept losing)

These are *targets*. Game-day exercises (P2) will confirm or revise.

---

## Per-data-class targets

| Data class | Examples | RTO | RPO | Backup mechanism |
|---|---|---|---|---|
| **Auth / identity** | workers, hive memberships, role grants | 15 min | 0 (zero-loss) | Supabase point-in-time recovery + daily logical dump |
| **Active operational** | logbook_entries, work_orders, inventory_transactions | 1 hour | 5 min | Supabase PITR (7-day window on Pro) |
| **Analytics / derived** | v_kpi_truth_* views, canonical_period_summaries | 4 hours | 1 hour | Recomputable from source tables |
| **Companion / voice** | wh_voice_*, agent_memory, agent_episodic_memory | 4 hours | 15 min | Recomputable / regenerable on next interaction |
| **Archive** | cold_archive Parquet (DuckDB) | 24 hours | 24 hours | S3 / R2 versioned bucket |
| **Logs / observability** | wh_traces, agentic_rag_traces, audit-log | 24 hours | 1 hour | Daily export to cold storage; 30-day hot retention |

---

## Per-surface availability targets

| Surface | Availability target | Acceptable downtime per quarter |
|---|---|---|
| Auth (sign-in, hive switch) | 99.95% | 65 min |
| Logbook write | 99.9% | 2.2 hours |
| Real-time dashboards | 99.5% | 11 hours |
| Companion voice | 99.0% | 22 hours |
| Marketplace transactions | 99.95% | 65 min |
| Analytics reports | 99.0% | 22 hours |
| Public site (index, about) | 99.99% | 13 min |

---

## Recovery scenarios

### Scenario A — Single edge fn down (e.g. ai-gateway 5xx)
- **Detection:** /health endpoint + alert-hub (already shipped)
- **Recovery:** redeploy previous version via `deploy-functions.ps1` (rollback runbook P2)
- **Expected RTO:** 10 min
- **Data loss:** none (writes queued by `offline-queue.js`)

### Scenario B — Supabase region outage (Seoul)
- **Detection:** all health endpoints fail
- **Recovery:** cross-region failover (P3 deliverable) OR wait for Supabase recovery
- **Expected RTO:** 1–4 hours (depending on Supabase ETR)
- **Data loss:** ≤5 min (PITR)

### Scenario C — Bad migration shipped to prod
- **Detection:** Layer 0 fast guardian fails on next run; users see errors
- **Recovery:** PITR restore to pre-migration timestamp; investigate offline
- **Expected RTO:** 30–60 min
- **Data loss:** equal to (now − PITR target time); pick the floor

### Scenario D — Free-tier LLM chain exhausted
- **Detection:** rate-limit errors > 10% over 5 min
- **Recovery:** automatic fallthrough to OpenRouter :free (already shipped) → P3 Ollama self-host
- **Expected RTO:** 0 (degraded continues), full restore at provider reset
- **Data loss:** none; companion turns may be slower but complete

### Scenario E — Cross-hive data leak detected
- **Detection:** journey-hive-isolation-property.spec.ts FAIL OR customer report
- **Recovery:** STOP all writes; investigate; PITR restore impacted rows; notify affected hives
- **Expected RTO:** 4 hours
- **Data loss:** none (forward-only correction)

---

## Game-day cadence

Quarterly tabletop exercises simulate each scenario. Each game day:
1. Pick scenario.
2. Inject the failure on staging.
3. Run the recovery runbook with a stopwatch.
4. Update this doc with actuals.

First game day: **2026-Q3**, scenario B (region outage simulation).

---

## References

- [CAPACITY_PLAN.md](CAPACITY_PLAN.md)
- [UNIFIED_MEGA_GATE.md](UNIFIED_MEGA_GATE.md)
- Supabase Pro PITR docs: https://supabase.com/docs/guides/platform/backups
