# V-Axis Matrix — §13 P4/P5 (Journey × Layer)

_Generated 2026-06-21T00:42:48.469503+00:00 by `tools/journey_vaxis.py`._

> Each cell is FALSIFIABLE: **✓ proven** = a live psql/edge check passes this run · **· attributed** = a recorded proof artifact exists on disk (auto-degrades to blank if removed) · **– n/a** = the journey does not architecturally traverse this layer (stated reason; leaves the denominator) · **(blank) pending** = honestly unproven. No hand-marked greens (§13.5). 100% = every APPLICABLE cell proven-or-attributed.

## Measured

| Number | Value |
|---|---|
| applicable cells | 77 − 10 n/a = **67** |
| **V · strict** (proven-live / applicable) | **56/67 = 83.6%** |
| V · covered (proven+attributed / applicable) | 67/67 = 100.0% |
| pending | 0/67 |

## Matrix

| Journey | F | A | D | AU | C | CA | RL | S | L | AV | LB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **J1** Breakdown→Resolution | · | ✓ | ✓ | ✓ | · | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **J2** PM cycle | · | ✓ | ✓ | ✓ | · | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **J3** Marketplace txn | · | ✓ | ✓ | ✓ | – | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **J4** Voice pipeline | · | ✓ | ✓ | ✓ | · | – | ✓ | ✓ | ✓ | ✓ | – |
| **J5** Cross-hive isolation | · | ✓ | ✓ | ✓ | · | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **J6** Resilience | · | ✓ | · | – | – | – | ✓ | – | ✓ | ✓ | – |
| **J7** Scale | – | ✓ | ✓ | ✓ | – | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## Cell evidence (proven + attributed)

- **J1·F** (attributed) — rendered tile == DB canonical on hive.html (Playwright+postgres; vaxis_render_proofs.json[J1])
- **J1·A** (proven) — POST /ai-gateway {} → HTTP 400 canonical envelope ({"error":"Missing agent"})
- **J1·D** (proven) — logbook row persisted (status=Open)
- **J1·AU** (proven) — v_logbook_truth scoped to own hive shows the row (=1)
- **J1·C** (attributed) — Companion grounded answer proven (FAB≈0.5%/DEFL≈0% companion arc) [.last-companion-gate-pass, grounded_sweep_locks.json]
- **J1·CA** (proven) — open-jobs 25→26 (+1) for own hive
- **J1·RL** (proven) — over-cap solo bucket → HTTP 429 scope=solo (token-free 429, pre-LLM); neighbor bucket untouched (7=7, per-identity isolation); deny path no-increment (victim=999)
- **J1·S** (proven) — other hive cannot see the row (cross=0); its open-jobs unchanged (19→19)
- **J1·L** (proven) — wh_traces carries journey/J1 (status=200) scoped to own hive (own=1); invisible to other hive (cross=0)
- **J1·AV** (proven) — GET /ai-gateway/health → HTTP 200 ok:True deps[supabase,groq,cerebras]
- **J1·LB** (proven) — live burst 200 req (8 concurrent) → 224 rps, p95 46ms (SLO<2000), err 0.00% (SLO<1%)
- **J2·F** (attributed) — rendered tile == DB canonical on pm-scheduler.html (Playwright+postgres; vaxis_render_proofs.json[J2])
- **J2·A** (proven) — POST /analytics-orchestrator {} → HTTP 400 canonical envelope ({"error":"Missing required field: phase"})
- **J2·D** (proven) — anchor_date moved (2026-03-31→2025-06-11)
- **J2·AU** (proven) — scope item reads overdue scoped to own hive (=1)
- **J2·C** (attributed) — Companion grounded answer proven (FAB≈0.5%/DEFL≈0% companion arc) [.last-companion-gate-pass, grounded_sweep_locks.json]
- **J2·CA** (proven) — pm_overdue 23→24 (+1)
- **J2·RL** (proven) — over-cap solo bucket → HTTP 429 scope=solo (token-free 429, pre-LLM); neighbor bucket untouched (7=7, per-identity isolation); deny path no-increment (victim=999)
- **J2·S** (proven) — item invisible to other hive (cross=0); its pm_overdue unchanged (30→30)
- **J2·L** (proven) — wh_traces carries journey/J2 (status=200) scoped to own hive (own=1); invisible to other hive (cross=0)
- **J2·AV** (proven) — GET /analytics-orchestrator/health → HTTP 200 ok:True deps[supabase,ai-chain]
- **J2·LB** (proven) — live burst 200 req (8 concurrent) → 224 rps, p95 46ms (SLO<2000), err 0.00% (SLO<1%)
- **J3·F** (attributed) — rendered tile == DB canonical on marketplace.html (Playwright+postgres; vaxis_render_proofs.json[J3])
- **J3·A** (proven) — POST /platform-gateway {} → HTTP 400 canonical envelope ({"error":"Missing fn"})
- **J3·D** (proven) — published listing row exists (=1)
- **J3·AU** (proven) — seller visible scoped to own hive (=1)
- **J3·CA** (proven) — active_listings_count 0→1 (+1, published rollup)
- **J3·RL** (proven) — over-cap solo bucket → HTTP 429 scope=solo (token-free 429, pre-LLM); neighbor bucket untouched (7=7, per-identity isolation); deny path no-increment (victim=999)
- **J3·S** (proven) — seller invisible to other hive (cross=0)
- **J3·L** (proven) — wh_traces carries journey/J3 (status=200) scoped to own hive (own=1); invisible to other hive (cross=0)
- **J3·AV** (proven) — GET /platform-gateway/health → HTTP 200 ok:True deps[supabase]
- **J3·LB** (proven) — live burst 200 req (8 concurrent) → 224 rps, p95 46ms (SLO<2000), err 0.00% (SLO<1%)
- **J4·F** (attributed) — rendered tile == DB canonical on voice-journal.html (Playwright+postgres; vaxis_render_proofs.json[J4])
- **J4·A** (proven) — POST /voice-action-router {} → HTTP 400 canonical envelope ({"error":"Missing required field: transcript"})
- **J4·D** (proven) — voice transcript persisted (transcript==__VX__J4_63c2a9ec1…)
- **J4·AU** (proven) — entry visible scoped to its own auth_uid (=1)
- **J4·C** (attributed) — voice→bge-local embedding→companion grounding proven (companion arc ⑥) [.last-companion-gate-pass, grounded_sweep_locks.json]
- **J4·RL** (proven) — over-cap solo bucket → HTTP 429 scope=solo (token-free 429, pre-LLM); neighbor bucket untouched (7=7, per-identity isolation); deny path no-increment (victim=999)
- **J4·S** (proven) — another user's auth_uid cannot see the entry (cross=0; Pillar-R IDOR isolation)
- **J4·L** (proven) — wh_traces carries journey/J4 (status=200) scoped to own hive (own=1); invisible to other hive (cross=0)
- **J4·AV** (proven) — GET /voice-action-router/health → HTTP 200 ok:True deps[supabase,ai-chain]
- **J5·F** (attributed) — rendered tile == DB canonical on hive.html (Playwright+postgres; vaxis_render_proofs.json[J5])
- **J5·A** (proven) — POST /platform-gateway {} → HTTP 400 canonical envelope ({"error":"Missing fn"})
- **J5·D** (proven) — sensitive row exists in hive A (=1)
- **J5·AU** (proven) — own-hive scope sees the row (=1)
- **J5·C** (attributed) — Companion grounded answer proven (FAB≈0.5%/DEFL≈0% companion arc) [.last-companion-gate-pass, grounded_sweep_locks.json]
- **J5·CA** (proven) — hive B aggregate isolated from hive A's write (1100→1100)
- **J5·RL** (proven) — over-cap solo bucket → HTTP 429 scope=solo (token-free 429, pre-LLM); neighbor bucket untouched (7=7, per-identity isolation); deny path no-increment (victim=999)
- **J5·S** (proven) — hive B cannot see hive A's row (cross=0); B total unchanged (1100→1100)
- **J5·L** (proven) — wh_traces carries journey/J5 (status=200) scoped to own hive (own=1); invisible to other hive (cross=0)
- **J5·AV** (proven) — GET /platform-gateway/health → HTTP 200 ok:True deps[supabase]
- **J5·LB** (proven) — live burst 200 req (8 concurrent) → 224 rps, p95 46ms (SLO<2000), err 0.00% (SLO<1%)
- **J6·F** (attributed) — rendered tile == DB canonical on status.html (Playwright+postgres; vaxis_render_proofs.json[J6])
- **J6·A** (proven) — POST /ai-gateway {} → HTTP 400 canonical envelope ({"error":"Missing agent"})
- **J6·D** (attributed) — offline write-queue → IndexedDB enqueue/drain + sync replay (Tier-7 resilience) [offline-queue.js, tests/journey-offline.spec.ts]
- **J6·RL** (proven) — over-cap solo bucket → HTTP 429 scope=solo (token-free 429, pre-LLM); neighbor bucket untouched (7=7, per-identity isolation); deny path no-increment (victim=999)
- **J6·L** (proven) — wh_traces carries journey/J6 (status=429, rate_limited) scoped to own hive (own=1); invisible to other hive (cross=0)
- **J6·AV** (proven) — GET /ai-gateway/health → HTTP 200 ok:True deps[supabase,groq,cerebras]
- **J7·A** (proven) — POST /ai-gateway {} → HTTP 400 canonical envelope ({"error":"Missing agent"})
- **J7·D** (proven) — 12 concurrent inserts → 12 rows landed (no lost writes)
- **J7·AU** (proven) — all 12 burst rows scoped to own hive (= 12)
- **J7·CA** (proven) — truth-view aggregate over the burst = 12 (= 12)
- **J7·RL** (proven) — over-cap solo bucket → HTTP 429 scope=solo (token-free 429, pre-LLM); neighbor bucket untouched (7=7, per-identity isolation); deny path no-increment (victim=999)
- **J7·S** (proven) — burst invisible to other hive (cross=0); its total unchanged (1100→1100)
- **J7·L** (proven) — wh_traces carries journey/J7 (status=200) scoped to own hive (own=1); invisible to other hive (cross=0)
- **J7·AV** (proven) — GET /ai-gateway/health → HTTP 200 ok:True deps[supabase,groq,cerebras]
- **J7·LB** (proven) — live burst 200 req (8 concurrent) → 224 rps, p95 46ms (SLO<2000), err 0.00% (SLO<1%)

## N/A — architecturally not traversed (excluded from the denominator)

- **J3·C** — the marketplace txn journey does not traverse the LLM grounding layer (companion's semantic registry excludes marketplace listings)
- **J4·CA** — voice is RAG-embedding input — it produces NO aggregated KPI truth-view metric; voice correctness lives in D (row persists) + S (auth_uid isolation) + C (grounding)
- **J4·LB** — voice pipeline is not a platform load-target — load_probe drives the gateway (J7's axis)
- **J6·AU** — resilience is cross-tenant recovery infra — not a per-hive scoping path
- **J6·C** — resilience does not traverse the LLM grounding layer
- **J6·CA** — resilience does not aggregate domain data (no KPI roll-up on this journey)
- **J6·S** — cross-hive isolation is J5's axis, not the offline/429 recovery journey
- **J6·LB** — load/scale is J7's axis; J6 is offline-queue + 429 recovery
- **J7·F** — concurrency/scale has no bespoke UI surface — there is no 'scale page' to render
- **J7·C** — the scale journey does not traverse the LLM grounding layer
