# WorkHive Capacity Plan

**Status:** v0.1 draft (P1 roadmap 2026-05-26)
**Owner:** Ian + Claude
**Reviewed:** monthly; refreshed quarterly

This document declares what load WorkHive supports today, what breaks first
as scale grows, and where the next investment is required. Numbers are
estimates pending a real load test (P2 deliverable).

---

## 1. Current shape

| Resource | Current | Comfortable ceiling | Hard ceiling |
|---|---|---|---|
| Concurrent hives | 5–10 (dev) | 50 | 200 (Supabase Pro tier) |
| Workers per hive | 1–20 | 100 | 500 (Realtime channels) |
| Voice companion turns / hive / hour | 50 (rate-limit cap) | 200 (with per-user) | 500 (free-tier LLM chain) |
| RAG flywheel turns / day | 50 (one full sweep) | 100 | 200 (provider TPM) |
| Edge fn cold start (p50) | 400–800 ms | 400 ms | 1500 ms |
| Supabase DB connections | 50 (pooler) | 200 | 400 (project max) |
| Realtime subscriptions | 100 (per project) | 500 | 1000 |
| Logbook entries / hive / day | 50–200 | 2000 | 10000 (page query needs index) |

---

## 2. What breaks first as scale grows

Ordered by failure probability, soonest first:

1. **Free-tier LLM TPM** — Groq + Cerebras + SambaNova combined ceiling is ~1M TPM
   per minute aggregated. Above ~5 active hives running companion concurrently
   we exhaust the chain and fall through to OpenRouter :free (much slower).
   **Mitigation:** P1 LLM response cache (deterministic prompts) + per-hive
   token budget.

2. **Supabase Realtime channels** — voice-presence + alert-hub + companion
   handoff each open a channel. At 100 concurrent hives × 5 channels =
   500 channels. Project ceiling is 1000 on Pro.
   **Mitigation:** consolidate per-hive channels into one multiplexed
   channel (P2 realtime work).

3. **Cold-start latency** — ai-gateway, agentic-rag-loop, voice-handler all
   exceed 800ms cold. Companion UX dies above 1.5s.
   **Mitigation:** P1 LLM cache + P2 cold-start memoization extension.

4. **Page render budget** — 5 pages already approach the 150KB HTML
   ceiling. New features push them over.
   **Mitigation:** P1 render-budget validator (just shipped).

5. **DB write amplification** — voice traffic now writes ~5 rows per turn
   (presence, audit, memory, trace, transcript). At 500 turns/hour/hive
   × 50 hives = 125k writes/hour.
   **Mitigation:** P2 hot/warm/cold tiering activation.

---

## 3. Load test plan (P2 deliverable)

Run k6 or Artillery against staging with synthetic traffic:

| Scenario | Duration | Concurrency | Pass criteria |
|---|---|---|---|
| Voice companion sustained | 30 min | 20 simulated workers across 5 hives | p95 latency <2s, error rate <1% |
| RAG flywheel + companion | 10 min | flywheel + 10 workers | no rate-limit fallthrough below 80% chain |
| Logbook write burst | 5 min | 100 concurrent workers, 1 entry/sec | no realtime channel drops, no DB connection saturation |
| Mixed-page browsing | 15 min | 200 simulated users, 1 page/30s | no edge fn cold-start visible to user |

---

## 4. Investment triggers

When any of these fire, the next investment moves into P1:

| Trigger | Investment |
|---|---|
| 3+ hives hit per-hive rate limit in one week | Per-hive token budget + Ollama fallback |
| Any edge fn p95 > 1.5s for 3+ days | Cold-start memoization extension |
| Realtime channel count > 700 | Channel multiplexing |
| Logbook query p95 > 800ms | Index audit + hot/warm/cold activation |
| HTML page > 200KB | Component library extraction |

---

## 5. Machine-checkable thresholds (Maturity Phase 1 — Reliability, 2026-06-16)

These markers turn the prose above into gate-enforceable contracts. The
`(LB, GH)` saturation ratchet and `(LB, GS)` load-resilience sentinel parse
them verbatim — do not rename without updating the validators.

- **SATURATION-ALARM:** realtime-channel headroom. Comfortable ceiling **500**,
  hard ceiling **1000** (project max). Alarm fires when projected peak channels
  (`realtime_surfaces × ~5 channels/surface × comfortable_hives`) exceeds 500,
  or when `leak_risk_surfaces > 0` (a `subscribe()` lost its teardown). Enforced
  by `validate_connection_pool_saturation.py` (leaks frozen at 0; surface count
  frozen — conscious re-baseline only).
- **LOAD-SLO:** sustained-load target p95 latency **< 2000 ms**, error rate
  **< 1%** at 8 concurrent workers (the `tools/load_probe.py` rig; last local
  run p95 28 ms / 0.00% err). Swap-ready for a k6-against-staging run.
- **DEGRADED-MODE:** under provider/connection saturation the platform sheds
  load gracefully rather than 5xx-storming — the free-tier chain rotates on
  429/503 (`_shared/ai-chain.ts`), the LLM cache serves repeats, and rate
  limits return 429 + Retry-After. No hard dependency may fail closed.

---

## 6. References

- [RTO_RPO_DECLARATION.md](RTO_RPO_DECLARATION.md) — availability targets
- [FREE_TIER_ONLY.md](FREE_TIER_ONLY.md) — LLM chain shape
- [UNIFIED_MEGA_GATE.md](UNIFIED_MEGA_GATE.md) — gate layers
