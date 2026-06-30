# Arc S — Resilience / Disaster-Recovery / Chaos

> **The 12th arc.** The prior arcs proved the platform is *correct* (Q: value-at-the-glass) and its
> *attack surface is right* (R: adversarial). **Arc S proves the system survives failure.** For a
> maintenance product — logbook entries, asset register, sensor data, PM records — **data loss = trust
> loss.** Arc L touched burst-resilience and Arc H touched AI provider-fallback, but no arc has swept,
> as **one ratcheted, adversarially-verified, measured-% frame**, *what happens when a dependency dies*,
> *can we restore*, *do we corrupt on partial failure*, and *what happens offline*.

_Spine doc. Scorer/harness: `tools/resilience_dr_sweep.py` (R0). Started 2026-06-24. LOCAL._
_Selected by `NEXT_ARC_STUDY_post_Q.md` §3 (Candidate B) — the recommended Phase-B pick (never swept;
data-loss is the worst failure for a maintenance product)._

---

## 0. Why this arc, and what already exists (measured, not assumed)

Arc S is **NOT greenfield.** The platform already has a "Pillar DR" base — 5 focused tools built
incrementally across the SaaS-Gateway and Arc-L work:

| Lens | Existing tool(s) | What it proves | Gap it leaves |
|---|---|---|---|
| **C** consistency | `validate_idempotency.py` (6-layer) | migration re-runnability · `external_sync` UNIQUE · webhook HMAC-before-read · upsert `onConflict` discipline · pm_completion dedup · scheduled-report dedup · external-API `Idempotency-Key` · webhook event-dedup | atomicity of **multi-step writes** (insert A then B, no txn); client **double-submit** beyond pm_completions; optimistic-UI divergence |
| **F** failure-tolerance | `tools/game_day.py` (4 drills) · `tools/perf_l5_llm_resilience.py` | the **AI gateway** fails safe (4xx not 5xx, auth holds, health recovers) · LLM fns shed graceful 429 on quota | every **other dependency** down-behavior — DB, Storage, Auth, Realtime, the python API, CDN libs |
| **R** recovery | `tools/verify_backups.py` · `ROLLBACK_RUNBOOK.md` | **schema** reproducible from migrations + `migration_hashes.json` lock; rollback runbook present | **data** backup/restore (the rows); measured **RPO/RTO**; storage-bucket backup; restore *drill* |
| **D** degradation | `sw.js` (service worker) | offline/PWA shell (extent TBD by R0) | **offline-write queue** (field-worker data-loss); reconnect auto-retry; per-page read-only/degraded mode |

**So what does Arc S *add*?** Three things the scattered base does NOT do — the same value-add shape as Arc R:

1. **One ratcheted, measured-% frame** across all four resilience lenses (the tools are scattered, each with
   its own exit contract; no single board says "the platform's resilience posture is N%").
2. **The un-swept failure modes** the scattered tools miss (the "Gap it leaves" column above) — especially
   **offline-write data-loss** (the field-worker trust killer), **multi-step write atomicity** (partial-write
   corruption), and **non-AI dependency-down behavior**.
3. **Adversarial verification** — every candidate finding is refuted-by-default before it's called a gap
   ("would a skeptic say this is already handled?"), exactly as Arc R/Q did.

---

## 1. Lenses & floors

| Lens | Question | Floor |
|---|---|---|
| **F — Failure-tolerance** | each external dependency down → graceful degraded state (clear message / fallback), never a white screen, infinite spinner, or 5xx crash. | **F 90** |
| **R — Recovery** | backup/restore proven; measured RPO/RTO; no silent data-loss window; a documented + drilled restore path for **data**, not just schema. | **R 95** |
| **C — Consistency** | writes idempotent; no partial-write corruption; exactly-once on retries; atomic multi-step writes; no double-submit. | **C 100** |
| **D — Degradation** | offline / read-only / queue-and-retry; the field-worker writes offline and the data survives + syncs on reconnect; PWA app-shell. | **D 85** |

Floors mirror the study (`NEXT_ARC_STUDY_post_Q.md` §3): **F90 / R95 / C100 / D85.** C runs at 100 because a
partial-write corruption or a lost write is a silent data-integrity failure — the worst class for a system of record.

---

## 2. Sub-layers

- **S1 — dependency-down behavior** (each external dep × its failure mode → graceful). _Lens F._
- **S2 — backup / restore** (data + schema; RPO/RTO; restore drill; storage). _Lens R._
- **S3 — idempotency / partial-failure** (atomic multi-step writes, double-submit, exactly-once). _Lens C._
- **S4 — offline / degraded** (offline-write queue, reconnect retry, read-only mode, PWA shell). _Lens D._
- **S5 — data-integrity-under-failure** (the cross-cutting "no corruption / no silent loss" assertions, folded
  into S2/S3). _Lenses R + C._

**Tooling:** chaos probes (`docker stop/start` — already routine), restore drills, the existing
`validate_idempotency` extended, `game_day.py` broadened beyond the gateway, `sw.js` audited, k6/curl burst
(Arc L). Adversarial-verify each finding (refute-by-default) before claiming a gap.

---

## 3. ★ MEASURED % SCOREBOARD (no rounding-up; honest denominators)

> **R0 baseline (locked 2026-06-24, `resilience_dr_baseline.json`) → after the find→fix→gate sweep.**
> Measured by `tools/resilience_dr_sweep.py` (18 cells). New failure modes with no gate yet score
> **MISSING** == unswept — measured-not-credited, so the honest baseline shows the gap rather than
> hiding it. The 3 cells that pass at R0 are the existing Pillar-DR base (game_day, verify_backups,
> validate_idempotency); the other 15 are the un-swept surfaces this arc builds gates for.

| Lens | R0 baseline | Floor | Cells passing at R0 | **After sweep (2026-06-24)** |
|---|---|---|---|---|
| **F — Failure-tolerance** | 20.0% (1/5) | 90 | `gateway_failsafe` (game_day) | **✅ 100.0% (5/5)** |
| **R — Recovery** | 25.0% (1/4) | 95 | `schema_backup` (verify_backups) | **✅ 100.0% (4/4)** |
| **C — Consistency** | 20.0% (1/5) | 100 | `idempotency_6layer` (validate_idempotency) | **✅ 100.0% (5/5)** |
| **D — Degradation** | 0.0% (0/4) | 85 | — | **✅ 100.0% (4/4)** |

**ARC S COMPLETE — all 4 floors met, baseline ratcheted to 100% (forward-only), no regression.** 15 new
gates + the aggregate board registered in `run_platform_checks` (group "Resilience / DR"). Board:
`tools/resilience_dr_sweep.py` → `PASS - all lens floors met, no regression`.

**Denominator (18 cells):** F = {gateway_failsafe, dependency_timeout, ai_alldown_degrade,
external_circuit_breaker, cdn_resilience} · R = {schema_backup, dr_claims_backed, data_backup_restore,
dataloss_detection} · C = {idempotency_6layer, atomic_multistep, optimistic_lock, dedup_constraints,
optimistic_ui_rollback} · D = {offline_write_queue, queue_retry_strategy, precache_coverage,
backend_degraded_mode}.

---

## 4. Find → Fix → Gate register (from the R0 mining fan-out, adversarially verified — refute-by-default)

42 candidate gaps mined across the 4 lenses; the **real / likely**, locally-fixable ones drive the sweep.
The R-lens "claimed-but-unimplemented" cluster (G1/G2/G3/G7) is the **keystone**: `RTO_RPO_DECLARATION.md`
*declares* recovery mechanisms (auth daily dump, log export, S3/R2 archive) that **do not exist** — a
false-sense doc, the exact Arc-Q/R anti-pattern (a claim masking an unmeasured/unbuilt axis). The fix is to
**build the local structure** (a logical data backup+restore tool, a data-loss detector) and a
`validate_dr_claims` gate that fails if any declaration lacks a backing implementation.

| # | Lens | Finding (mined id) | Sev | Verdict | Fix | Gate | Status |
|---|---|---|---|---|---|---|---|
| 1 | C | logbook optimistic-lock guard (gap-C-007) — **REFUTED on verification:** `ocUpdate` (utils.js) + `.eq('updated_at', _editingUpdatedAt)` already implement compare-and-set (PRODUCTION_FIXES #43); the mining flagged the offline fallback path | high | **refuted** | none needed | `validate_optimistic_lock` (locks the pattern) | ✅ |
| 2 | C | dedup-prone writes missing UNIQUE: `marketplace_orders.stripe_session_id` (C-004), `pm_completions` (C-005), `project_links(project_id,logbook_id)` (C-010) | high | real | migration UNIQUE + `.upsert(onConflict)` | `validate_dedup_constraints` | ✅ |
| 3 | C | multi-step writes non-atomic: pm-completion→logbook→link (C-001), inventory qty→txn (C-002), CMMS multi-insert (C-009) | crit | real | atomic RPC (BEGIN…COMMIT) | `validate_atomic_writes` | ✅ |
| 4 | C | optimistic UI render-before-confirm, no rollback → phantom-saved row on failure (C-006) | high | real | rollback DOM + toast on insert failure | `validate_optimistic_ui` | ✅ |
| 5 | F | `supabase.from()` has no `AbortSignal.timeout` → infinite hang on DB brownout (F-002) | high | real | timeout wrapper + degraded UI | `validate_dependency_timeout` | ✅ |
| 6 | F | ai-chain all-providers-down returns bare `'{}'` → silent (F-005) | high | real | return `{error}` + caller surfaces it | `validate_ai_alldown_degrade` | ✅ |
| 7 | F | no circuit-breaker for Stripe/Resend/CMMS; `provider-health.ts` pattern exists but unused (F-010) | med | real | reuse provider-health for external APIs | `validate_circuit_breaker` | ✅ |
| 8 | F | analytics page: python-API-down → silent generic error, no cached fallback (F-001) | crit | real | timeout + last-snapshot fallback + dep-status | `validate_dependency_timeout` | ✅ |
| 9 | R | **keystone:** `RTO_RPO_DECLARATION.md` claims auth daily-dump / log-export / S3-R2 archive that are NOT implemented (G1/G2/G3/G7) | crit | real | build local data backup+restore tool; gate every claim | `validate_dr_claims` + `validate_data_backup` | ✅ |
| 10 | R | no data-loss detection — silent row deletions unmonitored until PITR window expires (G6) | high | likely | rowcount-snapshot monitor + alert | `validate_dataloss_detection` | ✅ |
| 11 | D | `offline-queue.js` is **dead code** — never instantiated; 14 write pages have zero offline-write protection (D-001, D-006) | crit | real | wire the queue on write pages | `validate_offline_resilience` | ✅ |
| 12 | D | offline queue has no retry/backoff/dead-letter — failed item stuck forever (D-002) | crit | real | retry_count + backoff + stalled flag | `validate_offline_queue_retry` | ✅ |
| 13 | D | 30/37 pages not precached → blank offline; no backend-degraded mode (D-003, D-004) | high | likely | broaden sw.js precache + health-poll banner | `validate_precache_coverage` + `validate_degraded_mode` | ✅ |

_Full 42-gap register with evidence + refutation is in `resilience_dr_results.json` provenance + the R0 mining
output. Lower-severity / uncertain gaps (F-009 gateway opacity, D-007 manifest signaling, G9 PITR-window,
G10 cold-archive scaffolding) are tracked but below the floor-driving line._

---

## 5. Method (unchanged from the 11 prior arcs)

study → lock spine (this doc) → **R0** (denominator + scorer `tools/resilience_dr_sweep.py` + baseline) →
find → fix → gate → verify (adversarial, refute-by-default) → ratchet (forward-only baseline) → teach (skills) →
persist (memory + roadmap Part 0). Measured-% not vibes; every fix verified; no lens regresses.
