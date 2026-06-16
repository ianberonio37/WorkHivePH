# Gateway SLO & Error Budget

**Pillar O — Observability & SLO.** Part of the Full-Stack SaaS Gateway arc (see `FULLSTACK_SAAS_GATEWAY_ROADMAP.md` §6, Phase 3). This doc declares the service-level objectives the gateway is held to, the error budget that follows, and exactly how each is measured. It is intentionally **grounded in instruments that already exist** (the `/health` surface, `tools/load_test.k6.js` thresholds, `provider-health.ts`, the `wh_traces` trace log) — it invents no new target it cannot measure.

**Status:** targets DECLARED + measurable; continuous SLO *aggregation* (a rollup dashboard / status page) is the remaining Phase-3 build. This doc + the local status page + structured-log breadth together close Pillar O.

---

## 1. Service-Level Indicators (SLIs) — what we measure

| SLI | Definition | Source of truth |
|---|---|---|
| **Availability** | % of gateway requests that return a non-5xx within timeout | `wh_traces` rows (one per gateway call) + `/health` probes |
| **Latency (interactive)** | p95 / p99 wall-clock for voice/companion turns through `ai-gateway` | `ai_cost_log.latency_ms` + k6 `voice_companion_latency_ms` |
| **Latency (RAG/background)** | p95 for `agentic-rag-loop` and batch flows | k6 `rag_flywheel_latency_ms` |
| **Error rate** | non-2xx (excluding intended 401/403/429) / total | `wh_traces` + k6 `http_req_failed` |
| **Provider health** | fraction of upstream LLM slots NOT in escalating-cooldown | `provider-health.ts` `getSlotHealthSnapshot()` |
| **Cache hit-rate** | `ai_cache` hits / (hits + misses) on cacheable routes | `ai_cache.hit_count` deltas |

## 2. Objectives (SLOs) — the targets, over a rolling 28-day window

| Objective | Target | Rationale / source |
|---|---|---|
| Gateway availability | **99.5%** | Free-tier upstreams + PH mobile reality; honest, not aspirational 99.99% |
| Interactive p95 latency | **< 2.0 s** | matches `load_test.k6.js` `http_req_duration p(95)<2000` |
| Interactive p95 (voice surface) | **< 2.5 s** | k6 `{scenario:voice_companion} p(95)<2500` |
| RAG/background p95 latency | **< 5.0 s** | k6 `{scenario:rag_flywheel} p(95)<5000` |
| Error rate | **< 1.0%** | k6 `http_req_failed rate<0.01` |
| Provider-chain success before fallback | **≥ 80%** | k6 pass-criterion "no rate-limit fall-through below 80% chain success" |

Intended rejections — `401` (auth), `403` (tenancy), `429` (rate-limit/quota) — are **policy working as designed** and are EXCLUDED from the error-rate SLI. They are tracked separately as policy-enforcement counters (Pillars I/P), not failures.

## 3. Error budget

A **99.5%** availability SLO over 28 days = an error budget of **~0.5% ≈ 3h 22m** of unavailability per window.

**Budget policy:**
- **Budget remaining** → ship freely; the gateway is within objective.
- **Budget < 25% remaining** → freeze non-essential edge-fn changes; prioritize resilience (cache adoption, circuit-break tuning, provider-chain breadth) until the budget recovers.
- **Budget exhausted** → only reliability fixes + rollbacks (see `ROLLBACK_RUNBOOK.md`) until the next window resets.

The error budget is the bridge between Pillar O (measure) and Pillar C (resilience) and Pillar DR (recovery): a burned budget is what triggers the C/DR levers.

## 4. How each objective is observed (local-first, no paid infra)

- **Per-request trace** — every gateway call writes a `wh_traces` row keyed by `trace_id` (Pillar R already threads it; verified live: `trace_id` returned from the browser). Availability + error-rate roll up from this table.
- **Synthetic latency/error** — `k6 run tools/load_test.k6.js -e BASE_URL=http://127.0.0.1:54321 -e ANON_KEY=…` against the LOCAL edge (the rig is NOT staging-blocked; it only needs the `k6` binary installed). Its thresholds ARE the latency/error SLOs above, so a green k6 run == SLOs met under synthetic load.
- **Provider health** — `provider-health.ts::getSlotHealthSnapshot()` exposes per-slot cooldown/penalty; surfaced on the status page (next build).
- **Cache hit-rate** — `SELECT model, hit_count FROM ai_cache` deltas (live-proven this arc: `voice-action-router` ~26×, `voice-report-intent` ~12× on a hit).

## 5. Remaining Pillar-O build (the punch-list this doc is part of)

1. ~~SLO / error-budget doc~~ — **this file** ✅
2. **Local status page** (`status.html`) — render `/health` for each edge fn + provider-health snapshot + last k6 result + error-budget burn. Local-first; no external status-page SaaS.
3. **Structured-log adoption breadth** — `_shared/logger.ts` adopted across ≥10 edge fns (measured by `fullstack_dev.py pillars`).
4. **Trace aggregation / store** — a queryable rollup over `wh_traces` (the availability/error SLI computation).

> Deploy of any of this stays Ian's call — everything here is local-first scaffolding and declared targets, not a prod action.
