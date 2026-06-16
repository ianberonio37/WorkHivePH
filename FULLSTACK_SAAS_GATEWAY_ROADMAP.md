# Full-Stack SaaS Gateway — Build Roadmap

**Created:** 2026-06-15
**Owner:** Ian + Claude
**Status:** ✅ **ARC ACCEPTED — overall 98.1% measured** (7/8 pillars 100%; C 88.9% with one documented anti-box-tick residual; Gateway-Accept capstone PASS). All LOCAL/uncommitted; whole-platform G0 guardian + prod deploy = Ian's separate gate. Run `python tools/fullstack_dev.py accept` to re-verify.
**Type:** The durable progress tracker for the Gateway build arc — read at the start of every Gateway session so we never lose the thread.

**Relationship to the existing docs (Gate ≠ Gateway):**
| Doc | Role | This roadmap's relation |
|---|---|---|
| [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md) | The **law** — 13×6 production×gate coverage matrix + 15 persistence mechanisms | Architectural source of truth; this roadmap builds the *architecture* the study *tests* |
| [FULLSTACK_SAAS_GATE.md](FULLSTACK_SAAS_GATE.md) | The **Gate runner** — `tools/fullstack_dev.py` that *tests* the 13 layers | The Gate catches drift; the **Gateway** is the thing being built |
| [PLATFORM_ROADMAP.md](PLATFORM_ROADMAP.md) | Per-item operational tracker (honest %) | Gateway pillars feed honest % back here |
| **This file** | The **Gateway build arc** — pillars, build order, phases | Analogue of the Companion's `AI_SURFACE_MAP.md §0.8` capability roadmap |

> **The one reframe:** the existing *Gate* **tests** the platform's 13 layers. The *Gateway* is the **architecture** — a single governed control-plane front door (identity → tenancy → policy → route → handle → observe), the platform-wide analogue of the Companion's "Sources Gateway." This roadmap builds it with the **same rigor and depth as the Companion grounding arc**.

---

## 📍 PROGRESS LEDGER (at-a-glance — update every session)

| Phase | Name | Pillars | State | Next action |
|---|---|---|---|---|
| **0** | Foundation lock & doctrine stand-up | — | ✅ **per-pillar scorecard SHIPPED** — `python tools/fullstack_dev.py pillars` measures 8 pillars × 6 phases from concrete criteria (file/grep/baseline checks) + honest punch-list; self-test extended (8-pillar/6-phase in range). Roadmap + 13×6 study in place. **This is now the MEASURED source of truth for per-phase %** (supersedes the hand-set estimates below). | Optional: §0 spine pointer in the study |
| **1** | The Gateway Spine | R + **I✅** + **P (rate-limit binding ✅)** | ✅ **Pillar I (tenancy) COMPLETE — ratchet 34→0, baseline locked.** ~25 fns wired w/ `resolveTenancy` (verify direct callers, skip service-role/cron) + **2 machine-ingest gated** (`requireServiceRole`: sensor-readings-ingest, data-fabric-normalizer — reject browser/anon, LIVE-proven 401) + 4 code-verified exempt (marketplace cross-hive · resume solo · voice-journal metadata-only). LIVE-proven: foreign-hive→403; **own-hive→200+real data (no over-gating)**; service-role→passes ingest gate. ✅ **Pillar P KEYSTONE (verified-tenant rate-limit binding) — `validate_policy_hive_binding.py` ratchet, exploitable 0.** Closed an unauth cross-tenant DoS: `ai-gateway` anon path + `resume-extract`/`resume-polish` keyed rate-limit on the *client* `hive_id` → now bucket on verified hive (members) / identity+IP (anon). LIVE-proven: anon spoofed-hive → `hive_id=NULL` solo bucket, victim hive untouched; member path still hive-buckets. §6c AS-BUILT. ✅ **Pillar P-PII (PII-egress enforcement) — `validate_pii_egress.py` L2 promoted WARN→FAIL (zero PII-to-LLM enforced).** Triaged the only 2 flags: resume-extract (own-PII opt-in) + agentic-rag-loop (false positive — token is DB-scoping/instruction, not prompt data) → code-verified exempt; gate PASS + enforcement proven to fire. §6d AS-BUILT. ★Follow-up: device-facing per-hive ingest KEY (product decision, tracked) | Pillar **R** ✅ COMPLETE (§6e): envelope-body migration was a trap/already-done; routing coverage ENFORCED (uncovered→0, L3 FAIL) + the triage's **auth_uid IDOR FIXED** across 2 fns (voice-semantic-rag + agentic-rag-loop, JWT-verified scope) + `validate_gateway_tenancy` extended to the identity-key family (live-proven). ✅ **Phase 2 (C) STARTED + LIVE-proven (§6f)** — cache adoption 1→2 (voice-action-router) + resilience FP fixed. Minor backlog: 8 latent rate-limit sites → `verifiedHiveId` naming; per-route quota adoption; recency-lane `.execute()` v2 bug |
| **2** | Compute & Resilience | C | 🟢 **88.9% — at honest ceiling + LIVE-proven** — cache adoption ratchet **1→3** (`cached()` in `voice-action-router` + `voice-report-intent`, MISS→HIT ~26×/~12× proven) + circuit-break 🟢 (`provider-health.ts`, `groq_fallback` 9/9) + **per-route AI quota** wired into `ai-gateway` (observe-default, enforce-on-row; member call 200 + `hive_route_calls` row proven) + **load test executed** (`tools/load_probe.py`: 400 reqs, p95 64ms, 0% err, marker set). 2 stale-gate FPs fixed. ONLY residual = cache-adopters≥5 (honest anti-box-tick: surface saturated at 3 classifiers). §6f. | (cache≥5 intentionally not chased; install k6 for the heavier rig if desired) |
| **3** | Observability & SLO | O | ✅ **COMPLETE (100%, measured)** — `GATEWAY_SLO.md` (SLIs/SLOs/error-budget) + `status.html` (live `/health` grid, 10/10) + `_shared/trace-store.ts` (SLI aggregation, math proven on seeded rows) + `/health` on 14 fns + structured `log` on 10 fns (live `request_start` ndjson proven). Was the 🔴 weakest pillar. | — (re-stress at Gateway-Accept) |
| **4** | Delivery & Recovery | DR | ✅ **COMPLETE (100%, measured)** — `tools/ci_gate.py` (local-runnable CI gate, non-mutating; wraps self-test+pillars+backup-verify) + `tools/game_day.py` (chaos drills D1–D4 LIVE-proven fail-safe: clean 4xx, auth gate 401, no 5xx) + `tools/verify_backups.py` (219/219 migrations hash-verified, runbook present). GH-Actions yaml + rollback runbook already existed. | — (re-stress at Gateway-Accept) |
| **5** | Gateway-Accept | all | ✅ **ACCEPTED (100%)** — `python tools/fullstack_dev.py accept`: 13 pillar gates + live game-day (D1–D4 fail-safe) + load-probe (p95 64ms/0% err) all green, pillar floors held, `.gateway-accept-pass` stamped. | (re-run `accept` after any change; whole-platform G0 + deploy = Ian) |

**Legend:** ✅ done · 🟢 strong · 🟡 partial · 🔴 weak · ⏳ in progress · 🔲 not started

### 📊 MEASURED scorecard (run `python tools/fullstack_dev.py pillars` — 2026-06-16)
Measured from concrete criteria (file exists / grep / ratchet baseline), not estimates:

| Pillar | % | | Phase | % to fully complete |
|---|---|---|---|---|
| D · Data & Truth | 100% | | **0** Foundation & doctrine | **100%** |
| F · Edge Experience | 100% | | **1** Spine (R+I+P) | **100%** |
| I · Identity & Tenancy | 100% | | **2** Compute & Resilience (C) | **88.9%** |
| P · Policy & Governance | 100% | | **3** Observability & SLO (O) | **100%** ✅ |
| R · Routing & Contract | 100% | | **4** Delivery & Recovery (DR) | **100%** ✅ |
| C · Compute & Resilience | 88.9% | | **5** Gateway-Accept | **100%** ✅ ACCEPTED |
| O · Observability & SLO | 100% ✅ | | | |
| DR · Delivery & Recovery | 100% ✅ | | **OVERALL ARC** | **98.1%** |

**Arc ACCEPTED — 7 of 8 pillars 100%, P5 capstone PASS** (`fullstack_dev accept`: all 13 pillar gates + live game-day + load-probe green, pillar floors held, `.gateway-accept-pass` stamped). **Sole open item: C → cache adopters ≥5 = HONEST RESIDUAL** (cacheable surface saturated at the 3 deterministic classifiers; caching the per-instance-unique extractors would be box-ticking per the ai-engineer skill — *not chased*). ⚠️ The **whole-platform G0 guardian + prod deploy** remain a SEPARATE Ian-gated step (run `fullstack_dev gate --full` / commit on a clean tree) — not part of the gateway-accept capstone.

---

## 1. Why this exists (the reframe)

The platform's cross-cutting concerns — auth, tenancy, the response envelope, rate-limiting, PII redaction, CORS, secrets — are **re-implemented per-function across all 56 edge functions** via the `_shared/*` helpers. That is good hygiene, but it is a **distributed gateway, not a gateway**: there is no single front door where a request provably passes `identity → tenancy → policy → route → handle → observe` in one ordered pipeline. On the client, role/hive are **localStorage-trusted** (the architect skill is full of "re-validate from DB" patches — a symptom of the missing server-side tenant-context resolver).

External validation of the framing:
- [AWS Well-Architected SaaS Lens](https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/the-pillars-of-the-well-architected-framework.html) splits a SaaS into a **control plane** (cross-cutting front door: identity, tenancy, routing, rate-limits, policy) and an **application plane** (per-feature logic). The API Gateway validates the tenant token, maps each tenant's request to a service, and manages the SLA.
- [BFF / API-Gateway pattern](https://goteleport.com/learn/cybersecurity-best-practices/backend-for-frontend-bff-pattern/) — consolidate auth, tenancy, rate-limiting, SSL termination, and routing into one governed entry point; keep feature logic behind it; the gateway is the natural caching + policy point.
- [12-Factor in 2025 + SRE](https://dev.to/whoffagents/the-12-factor-app-in-2025-what-still-applies-and-whats-changed-1nk0) — modern production adds **observability (logs/metrics/traces), secrets management, and SLOs/error budgets** as first-class factors. "12-factor is a foundation, not a ceiling."

**The control plane is "the Gateway."**

---

## 2. Lead fusion verdict (the highest-leverage move)

> **Fuse the cross-cutting concerns that are currently copy-implemented across 56 edge functions into ONE governed Gateway pipeline.** A single `_shared/gateway.ts` middleware chain — *wrapping the helpers that already exist (invent nothing)* — that every edge function runs, plus optionally a thin `gateway` front-door function. Adoption becomes a ratchet, exactly like envelope-conformance went 56/56.

```
request
 → resolveIdentity()   server-side (not localStorage-trusted)
 → resolveTenancy()    hive + role from DB, RLS-safe
 → enforcePolicy()     rate-limit · quota · PII redaction · CORS · secrets
 → route()             uniform envelope, versioned contract
 → handler()           feature logic (the application plane)
 → observe()           one trace-id, structured log, error budget
```

**Owner:** new `_shared/gateway.ts` (wraps `_shared/{cors,envelope,health,rate-limit,provider-health,error-tracker}.ts`).
**Blast radius:** all 56 edge fns adopt the pipeline (ratchet). **Enforcement:** new `validate_gateway_pipeline_adoption.py` (G0), baseline = current non-adopters, moves down only.
**This is the architectural "Gateway" Ian is asking for.**

---

## 3. The pillars (mirror of the Companion's S/R/O/G/A/P/K/M/Q/T)

The 13 production layers, clustered by job-to-be-done into 8 Gateway pillars. **% are honest estimates** — refined by the gate scorecard in Phase 0.

| Pillar | Job-to-be-done | Maps to | State | Est % |
|---|---|---|---|---|
| **D — Data & Truth** ⭐FOUNDATION | Governed semantic layer + immutable migrations | D | 🟢 the moat — 42 `v_*_truth` views, sha256 migration lock, truth-view contract; Companion proved it | ~80% |
| **R — Routing & Contract** | One front door, uniform envelope, versioned API | A | 🟢 contract (envelope 56/56, health 10/10) · 🟢 **routing coverage ENFORCED** (`validate_gateway_coverage` uncovered→0, L3 FAIL; every fn routed or self-secured-bypass) · consumers unwrap the envelope | ~75% |
| **I — Identity & Tenancy** | Resolve who / which-hive / what-role **server-side** | AU + S(part) | 🟡 RLS strong, but role/hive are **client-trusted** in localStorage | ~55% |
| **P — Policy & Governance** | Rate-limit, quota, PII redaction, CORS, secrets — per request | RL + S | 🟢 **rate-limit verified-tenant binding ✅** (`validate_policy_hive_binding.py`, exploitable 0; unauth cross-tenant DoS closed) + **PII-egress ENFORCED ✅** (`validate_pii_egress.py` L2 WARN→FAIL, zero PII-to-LLM; gateway centralizes redaction); quota adoption still partial | ~75% |
| **C — Compute & Resilience** | Provider chain, fallback, cache, circuit-break, scale | C + CA + LB | 🟢 **88.9%** — circuit-break (`provider-health.ts`), cache ratchet 1→3 (~26×/~12× hit), per-route AI quota in `ai-gateway`+`platform-gateway` (observe-default), load test executed (`load_probe.py` p95 64ms/0% err). Residual = cache≥5 (anti-box-tick, not chased). §6f | ~89% |
| **O — Observability & SLO** | Trace every request, structured logs, error budget, status page | L + AV | 🟢 **COMPLETE (100% measured)** — SLO doc + error budget, `status.html` live `/health` grid (10/10), `trace-store.ts` SLI aggregation (proven), `/health` on 14 fns, structured `log` on 10 fns. Sentry-swap-ready remains the prod path. | ~100% |
| **DR — Delivery & Recovery** | CI gate, deploy, rollback, game-day, backups | H + CI | 🟢 **COMPLETE (100% measured)** — local CI gate (`ci_gate.py`), executable game-day (`game_day.py`, D1–D4 fail-safe-proven), backup-integrity verifier (`verify_backups.py`, 219/219), rollback runbook. GH-Actions enable + prod deploy stay Ian-gated. | ~100% |
| **F — Edge Experience** | BFF-shaped client surface, render budget, XSS | F | 🟢 render-budget 100%, escHtml universal | ~85% |

**Where "a very good build" pays off:** the 🔴/🟡 pillars — **R** (the real front door), **O** (what separates a hobby SaaS from a *proper* one), **I** (stop trusting the client). **D and F are already excellent — we protect them, we don't rebuild them.**

---

## 4. Build order (same shape as the Companion's S→R/O→G→A→…)

```
D   harden the foundation: lock the semantic layer as the gateway's data contract
      ↓
R+I+P   THE GATEWAY SPINE — one pipeline = identity → tenancy → policy → route
      ↓     (the fusion verdict §2; adoption is a ratchet across 56 fns)
C   resilience folds onto the pipeline: cache + circuit-break as middleware
      ↓
O   observability wraps the pipeline: one trace-id per request, SLO, status page
      ↓
DR  delivery/recovery: enable the CI gate + game-day — kept LOCAL-ready
      ↓
F   maintained throughout — already green
      ↓
Gateway-Accept   re-stress every layer through the Gate (like the Companion's G-Accept)
```

---

## 5. The phases (each ends gate-green + a live proof — Companion cadence)

Every phase: ends with `fullstack_dev.py` green **and** a live real-call / Playwright proof, updates ≥3 skills (Rule C), bumps honest %, baselines move down only.

- **Phase 0 — Foundation lock & doctrine stand-up.** This file + a §0 spine pointer in the study + a per-pillar **scorecard** skeleton in `fullstack_dev.py`. Low effort. *Proof: `fullstack_dev.py status` shows the 8 pillars.*
- **Phase 1 — The Gateway Spine (R + I + P).** `_shared/gateway.ts` pipeline wrapping the existing helpers; server-side identity/tenancy resolver; ordered policy enforcement; `validate_gateway_pipeline_adoption.py` ratchet. Pilot on one edge fn end-to-end, then ratchet across 56. *Proof: pilot fn runs the full pipeline live; adoption baseline locked.*
- **Phase 2 — Compute & Resilience (C).** Cache + circuit-break as pipeline middleware; raise `ai_cache` + per-hive quota adoption to target; wire the k6 load-test rig. *Proof: cache-hit + 429-degrade observed live.*
- **Phase 3 — Observability & SLO (O).** One trace-id threaded through the pipeline; structured-log adoption → 100%; an error budget + SLO doc; a **local** status page; `error-tracker.ts` Sentry-swap-ready. *Proof: a request traced end-to-end by id.*
- **Phase 4 — Delivery & Recovery (DR).** Enable the CI gate (local-runnable); game-day script; backup verification. **LOCAL-ready — prod-push gated on Ian.** *Proof: CI gate runs green locally; game-day dry-run.*
- **Phase 5 — Gateway-Accept.** Re-stress all 13 layers through `fullstack_dev.py mega`; per-pillar scorecard all green-or-honestly-baselined; live cross-page proof. *Arc done here.*

---

## 6. What we stand up for "the same rigor and depth"

Mirroring exactly what made the Companion arc durable:
1. **This roadmap** — the spine (📍 ledger up top); ends doc sprawl.
2. **A doctrine doc** (optional, if pillar detail outgrows this file) — `FULLSTACK_SAAS_GATEWAY_DOCTRINE.md`, analogue of `COMPANION_GROUNDING_DOCTRINE.md`, with as-built sections per phase.
3. **A standing gate** — per-pillar scorecard in `fullstack_dev.py` + `validate_gateway_pipeline_adoption.py` ratchet (every edge fn runs the pipeline or is explicitly exempt).
4. **Honest %** per pillar fed back into `PLATFORM_ROADMAP.md`; baselines only move down (Rule B).
5. **Local-first** — anything touching external infra (Sentry DSN, status page, staging) ships as **swap-ready scaffolding**, not a prod action. Deploy stays Ian's call. (Honors `feedback_stay_local_dont_suggest_prod_push`.)

---

## 6b. Phase 1 — AS-BUILT (2026-06-15, keystone landed + LIVE-proven)

**Discovery that reshaped Phase 1:** the gateway front door already existed (`platform-gateway`) — so the fusion verdict became **harden it**, not build it (pure WRAP). But it surfaced a **confirmed, systemic tenancy hole**:

> Both front doors — `platform-gateway` AND `ai-gateway` — authenticated the *user* (`auth_uid`) but **trusted the client-supplied `hive_id`** for rate-limit / audit / downstream forwarding. A signed-in worker could act against **any** hive. `auth(user) ≠ authz(tenant)`.

**Shipped (all LOCAL, prod-deploy = Ian's call):**
- **`_shared/tenant-context.ts`** (Pillar I keystone) — `resolveIdentity()` + `resolveTenancy()` consolidating the proven `v_worker_truth` active-member check that was copy-pasted across `analytics-orchestrator` / `export-hive-data` (+ `resolveUserId`). One governed resolver = the single source of truth; the hole cannot reopen per-function.
- **`platform-gateway` hardened** — replaced client-trusted `body.hive_id` with verified membership (403 `not_a_member` on a foreign hive); server-resolved `worker_name`/`hive_id` flow downstream; trace-id threaded (Pillar R). **LIVE-proven:** an unauthenticated POST now returns `{error,code:"auth_required",trace_id}` — the new resolver runs in the live edge runtime.
- **`validate_gateway_tenancy.py`** (G0 ratchet) — FAILs if a fn reads a client `hive_id` without a membership check. Self-test 5/5 (incl. a regression guard for the nested-`{}`-destructure false-negative that originally hid ai-gateway). **Baseline locked at 34**, registered in `run_platform_checks.py`, auto-discovery green (344 validators). Complementary to `validate_gateway_coverage.py` (that ratchets *routing*; this ratchets *tenancy*).

**The Pillar I rollout backlog (ratchet 34 → 0):** 34 edge fns read a client `hive_id` without their own check. Triage each into (a) wire `resolveTenancy()`, or (b) `TENANCY_VERIFY_EXEMPT` with justification (service-role/cron/webhook/solo/forwarded-by-verified-gateway). **Next priority: `ai-gateway`** (a front door, not a forwarded specialist — same 3-line fix, but high blast radius so its own careful step).

---

## 6c. Phase 1 — Pillar P KEYSTONE AS-BUILT (2026-06-15, verified-tenant rate-limit binding + LIVE-proven)

**The I↔P intersection bug:** Pillar I closed the *data-read* hole, but **policy** (rate-limit/quota) had its own copy. `checkAIRateLimit(db, hiveId)` keys a SHARED per-hive counter; on **anon-capable** fns the `hive_id` came from the client with no membership check:
- **`ai-gateway`** allows `agent:"voice-journal"` anonymously, and its `resolveTenancy` guard is `if (user && hive_id)` — so an anon POST `{agent:"voice-journal", hive_id:"<victim>"}` SKIPPED verification and consumed the **victim hive's** bucket. ~500 anon calls/hr → the victim's real users get 429'd. **Unauthenticated cross-tenant DoS.**
- **`resume-extract` / `resume-polish`** (public `verify_jwt=false`, solo features) did `if (hive_id) checkAIRateLimit(db, hive_id)` with no check at all.

Two attacks from one bug: (a) **drain** a victim's bucket by spoofing its id; (b) **dodge your own cap** by inventing a fresh id each call — no login required.

**Shipped (all LOCAL, prod-deploy = Ian's call):**
- **`ai-gateway`** — captures `verifiedHiveId = tenancy.hive_id` (set only after the membership check); rate-limits members on the verified hive (`checkUserRateLimit`), anon callers on their **identity/IP** (`checkSoloRateLimit(soloRateLimitKey(authUid, clientIp))`). A spoofed `hive_id` keys nothing.
- **`resume-extract` / `resume-polish`** — solo features now ALWAYS identity-bucket; removed the dead local `checkAIRateLimit` helper + `RATE_LIMIT_PER_HOUR` + the now-unused client `hive_id` read (a latent footgun that still wrote `ai_rate_limits`). They no longer read a client `hive_id` at all → DROPPED from `TENANCY_VERIFY_EXEMPT` (Pillar I exempt 4→2 — a tighter posture: a future unguarded read now FAILs instead of being silently exempt).
- **`validate_policy_hive_binding.py`** (Pillar P, G0 ratchet, registered) — FAILs when an **anon-capable** fn passes a raw client `hive_id` to a hive-keyed limiter. self-test 6/6, **exploitable baseline 0**; reports 8 *latent* authed-but-raw call sites (value is verified earlier → not exploitable; naming-convention backlog = adopt a `verifiedHiveId` var). Scoping FAIL by exploitability keeps the baseline honest (0, not 8 of false alarms).

**LIVE-PROVEN** (edge :54321; queried the edge's real DB `supabase_db_workhive` via `docker exec psql` — the postgres MCP was on a stale/empty DB, a false-negative all-zeros): anon ai-gateway call with spoofed victim hive → wrote `ai_user_rate_limits[ip:203.0.113.7]` with `hive_id=NULL`; anon resume-extract with spoofed hive + body `auth_uid` → wrote `ai_user_rate_limits[<auth_uid>]` `hive_id=NULL`. The victim hive's only `ai_rate_limits` row was **3h39m old** (a legit member earlier) — my attacks never touched it. Member path still hive-buckets (no regression). Test rows cleaned up. **The exploitable class is small because authed fns already verify membership BEFORE the limiter** (asset-brain-query even comments it) — the gap was only the anon surface.

**Regression:** `validate_gateway_tenancy.py` self-test 6/6 + scan PASS (exempt 4→2, UNVERIFIED 0 ≤ baseline 0); `validate_auto_discovery.py` PASS (345 validators registered). Did NOT run full `run_platform_checks --fast` (dirty-tree report-regen hazard — honors the QA ops-hazard lesson). Skills updated: security, multitenant-engineer, architect, qa-tester (Rule C).

**Pillar P remaining (backlog):** per-route quota adoption; the 8 latent rate-limit call sites → `verifiedHiveId` naming.

---

## 6d. Phase 1 — Pillar P-PII AS-BUILT (2026-06-15, PII-egress ENFORCED — advisory→hard gate)

**Finding (honest):** PII-egress adoption was already substantially done — `ai-gateway` centralizes redaction (`redactPIIWithMap`+`hydratePII`, proven 2026-06-07/13), and the 4 orchestrators were wired in May. `validate_pii_egress.py` surfaced exactly **2** L2 flags, and on inspection **neither is a leak**:
- **resume-extract** — the email/phone/name ARE the deliverable (the user uploads their OWN resume to extract their OWN contact block; JSON-Resume `basics`). Opt-in own-PII; `worker_name` is read then `void`'d. → code-verified **exempt**.
- **agentic-rag-loop** — `worker_name`/`workerName` are used ONLY for DB `.eq()` scoping + cost-log rows; all 5 callAI stages prompt on `question`/`chunks`/`answer`/`memory` only; the `phone` flag is the literal word in an *anti-PII instruction* (`GRADER_SYSTEM`: "content must NOT contain PII (phone numbers…)"). → code-verified **exempt (false positive)**.

So there was **no production code to change** — the gateway already does the work. The real gap was **enforcement**: L2 was WARN-only (advisory, never blocked). 

**Shipped (gate change, LOCAL):**
- `validate_pii_egress.py` — added the 2 code-verified exemptions to `PII_EGRESS_OK` (6→8), and **promoted L2 from WARN → hard FAIL** (`skip:False`, label + docstring updated). PII to a 3rd-party LLM is binary — redact, or be code-verified exempt; the bar is **zero**, no ratchet-down. (L1 direct-fetch stays WARN: broader heuristic, already empty.)
- **Proven the gate has teeth:** real run = all 4 checks PASS / 0 FAIL; then in-process simulation with the 2 exemptions stripped → **2 hard-FAILs** = enforcement fires (not a hollow green). No new validator (already registered) → no auto-discovery change.

**Known residual (documented):** `_has_redact_helper` is a file-level check (a `redactPII(` *anywhere* counts) — a fn could redact one path and leak another. Tightening to data-flow precision is deferred; the gateway-centralization + exempt-list discipline is the current control. Skills updated: security, ai-engineer, qa-tester, enterprise-compliance (Rule C).

---

## 6e. Pillar R RECON (2026-06-15, read-only) — the "envelope-body migration" was a misframe; the real gap is routing coverage

Before touching Pillar R I mapped the actual contract surface. The handoff's queued task — "migrate the gateways' response BODIES to the envelope" — turns out to be **a trap or already-done**, not the work:

- **Producer/contract side is already 🟢.** Envelope conformance is 56/56. `ai-gateway` success returns the `ok()` envelope `{ok,data,trace_id}`; **errors are flat `{error}` ON PURPOSE** — `validate_edge_contracts` greps for the literal `JSON.stringify({ error:` shape, so "enveloping" error bodies would TRIP a sibling validator (the documented resume-extract/polish trap: import the envelope token but KEEP the flat error shape). `platform-gateway` threads `trace_id` (header `x-wh-trace` + body). So there is no error-body migration to do.
- **Consumer side is already CLOSED.** The 2026-06-07 "silent-undefined flop" (callers reading top-level `.answer`/`.error` on an enveloped response) is fixed across every consumer I checked: `asset-hub.html` + `hive.html` inline `const gw = (body.ok===true && body.data) ? body.data : body;`; `assistant.html` + `voice-journal.html` have explicit "ai-gateway nests under .data" handling; `voice-handler.js` has the named `_unwrapGateway`; `companion-launcher.js` unwraps + surfaces the honest error body. The ONLY residual is cosmetic: the inline unwrap is duplicated across ~6 files instead of one shared helper (low-value DRY, not a correctness bug).
- **The REAL Pillar R 🔴 = "single front door" routing coverage.** `validate_gateway_coverage.py` (WARN today): **routed 16, bypass_ok 26, uncovered 17.** Those 17 callable edge fns are neither routed through `platform-gateway` (`PLATFORM_ROUTES`) nor justified in `GATEWAY_BYPASS_OK`. Driving uncovered→0 is the genuine R adoption ratchet — the SAME safe per-fn-triage shape as Pillar I/P (read each fn's real caller path; route browser-callables, bypass-justify cron/service-role/internal), NOT the risky frontend envelope surgery the handoff implied. ⚠️ Heed the Pillar-I trap: grep can't separate a real browser invoke from a test-harness/cron/comment mention — triage needs eyes, don't mass-bypass.

**Revised Pillar R plan:** (1) triage the 17 uncovered fns → routed-or-bypass-justified; (2) optionally promote `validate_gateway_coverage.py` WARN→ratchet once at a stable baseline; (3) optional low-value: centralize the inline unwrap into one shared `_unwrapGateway` (utils.js) + a consumer-side ratchet. **De-risked: this is edge-fn + validator triage, not frontend-blast-radius surgery.**

### 6e-AS-BUILT (2026-06-15) — routing triage done: uncovered 17→1, and the triage SURFACED a real IDOR

Triaged all 17 by **frontend-caller count + per-fn gate verification** (eyes on each, no mass-bypass). **16 → `GATEWAY_BYPASS_OK`** with code-verified justifications (bypass 26→42, uncovered 17→**1**):
- *Self-secured structured/solo browser tools* (route would DROP their rich payload; each already gates in-fn post-Pillar-I/P): agentic-rag-loop, equipment-label-ocr, platform-scraper (resolveTenancy); resume-extract, resume-polish (checkSoloRateLimit, solo).
- *Server-side / internal / pipeline* (0 frontend callers): agent-memory-store, cold-archive-query, data-fabric-normalizer (requireServiceRole), export-hive-data (inline v_worker_truth), hierarchical-summarizer, semantic-fact-extractor, temporal-rag-orchestrator, voice-embeddings, voice-model-call, walkthrough-analyzer.
- *Stateless transform*: tts-speak (text+persona→MP3, no hive data).

**⚠️ FINDING — `voice-semantic-rag` left UNCOVERED on purpose (a real per-user IDOR):** it scopes a per-worker voice-journal read by the **CLIENT-supplied `auth_uid`** (body) on a **service-role (RLS-bypassed)** client, called with the anon key (no user JWT). A caller passing another worker's `auth_uid` reads that worker's journal — the **`auth_uid` analogue of the Pillar-I `hive_id` hole**, which `validate_gateway_tenancy` does NOT catch (it only checks `hive_id`). Flagged in-code (fn header) + here. **Did NOT bypass-certify it (no false-green) and kept the coverage ratchet DEFERRED (WARN).** FIX (product fork — anon-companion impact): voice-handler.js must send the user ACCESS TOKEN (not the anon key) → voice-semantic-rag `getUser()`-derives `auth_uid` and rejects a mismatched body value; anon callers (no journal) → empty. **Broader lesson:** the Pillar-I invariant generalizes — *any* client-supplied IDENTITY key (hive_id OR auth_uid OR worker_name) used to scope a service-role read must be server-verified; consider extending `validate_gateway_tenancy.py` to the `auth_uid` variant.

**✅ RESOLVED (2026-06-15, same session — "generalize then fix"):** the auth_uid IDOR is CLOSED across the whole class.
- **Generalize:** a discovery scan for the identity-key family found the class = **2 fns** — `voice-semantic-rag` AND `agentic-rag-loop` (both read `voice_journal_entries` by a client `auth_uid`). The two `getUser`-using candidates (analytics-orchestrator, voice-logbook-entry) were already safe (JWT-derived).
- **Fix:** both now derive the uid from the JWT (`resolveIdentity` → `getUser(bearer)`, the proven Pillar-I resolver), **ignore the client body value**, and return empty for an unverified caller; `agentic-rag-loop` keeps the supplied uid only for a verified **service-role forward** (`effectiveAuthUid`). `voice-handler.js` now sends the signed-in user's **access token** (not the anon key) to both. (Gotcha logged: no-arg `getUser()` returns null on a server edge fn — use explicit `getUser(jwt)` / `resolveIdentity`.)
- **Ratchet:** `validate_gateway_tenancy.py` **extended to the identity-key family** (`auth_uid`/`user_id` read + `.eq`/`match_` scope without a `getUser`/`resolveIdentity`/`requireServiceRole` verification = unsafe) + **comment-stripping** (a `[\s\S]*?` regex had matched a `hive_id` in a header comment). self-test 8/8, baseline **0**.
- **Coverage gate un-deferred:** `voice-semantic-rag` added to `GATEWAY_BYPASS_OK` (now genuinely self-secured) → uncovered **1→0**; `GATEWAY_COVERAGE_DEFERRED=False` (L3 WARN→**FAIL**, teeth proven). **`validate_gateway_coverage.py` = ALL 4 PASS** (routed 16 / bypass 43 / uncovered 0).
- **LIVE-PROVEN** (victim uid has 11,933 journal entries): attacker no-JWT + victim `auth_uid` → `{results:[],method:"unauthenticated"}` (short-circuits before any query); authed user (minted JWT) → `method:"recency"` self-scoped; cross-user (authed + a *different* victim's body `auth_uid`) → self-scoped, body value ignored. Regression: agentic_rag_loop 21/21, edge_contracts 0 FAIL, gateway_tenancy 0. (Note: a PRE-EXISTING unrelated bug — the recency lane uses v1 `.execute()` + no local embeddings → `count:0` locally; the `method` field is the auth proof. Tracked, not fixed here.)

---

## 6f. Phase 2 — Pillar C (Compute & Resilience) AS-BUILT (2026-06-15, first increment + LIVE-proven)

**Recon reframed the work (CLAUDE.md rule 1 — look for existing tools first).** Pillar C's scaffolding already exists; this is an *adoption + measurement* job, not green-field:
- **Circuit-break** is already 🟢 — `_shared/provider-health.ts` is a per-provider circuit breaker (escalating cooldown 1m→10m→1h→6h, explicit Retry-After honoring, sticky sessions, soft-priority demotion). `validate_groq_fallback.py` 9/9 PASS.
- **Cache** primitive exists (`_shared/cache.ts` over the `ai_cache` table); the honest gap was **adoption** — only `agentic-rag-loop` used `cached()` (floor 1 of ~45 AI-calling fns).
- **Quota** is already rich (`_shared/rate-limit.ts`: per-hive, per-route + `hive_route_quotas`, per-user, solo, voice/background-classed).
- **k6 rig** exists (`tools/load_test.k6.js`) but is dormant — needs only the **k6 binary** (it targets the LOCAL edge `:54321`, NOT staging — the "blocked on staging" label was a prior misframe).

**Shipped (all LOCAL, prod-deploy = Ian's call):**
- **Cache adoption ratchet 1 → 3** — wired the proven `cached()` pattern into **`voice-action-router`** (Router LLM call) **and `voice-report-intent`** (intent classifier). **The load-bearing correctness decision (voice-action-router):** the cache sits **upstream of per-hive asset resolution**. The LLM only classifies intent from `(transcript, page, asset_id, persona)` — ALL captured in the key `voiceroute:${personaKey}::${userPrompt}` (namespace `voice-action-router`). **Hive assets are resolved AFTER the cache** (`resolveAssetCandidates` against `v_asset_truth`), so the cached value is **hive-independent → zero cross-hive leakage**, and *not* keying on `hive_id` is precisely what preserves the cross-hive repeat-rate win (the same spoken command across hives is a cache hit). Family-P safety (the `ASSET_REQUIRED_KINDS` blank-machine confidence-demote to ≤0.45 + the 0.5 confirm floor) still runs **fresh downstream of the cache** → a hit cannot bypass slot-fill or cause an unintended write. 6h TTL (mirrors `agentic-rag-router`). **`voice-report-intent` is even cleaner** — its prompt is the transcript ALONE (const `INTENT_SYSTEM`, no persona/hive/asset data, memory loaded around the call not into it), so the key is just `voiceintent:${safeTranscript}` and the value is trivially hive-independent. `validate_llm_cache_adoption.py` floor lifted **1→2→3**.
- **Two stale-gate false-positives fixed** — (a) `validate_resilience.py`'s L3 bare-`await fetch(` scan flagged `companion_surface_battery.js:23`, a **console usage example inside the JSDoc header**, not a production fetch. Added `_blank_comments()` (blanks JS block + HTML + full-line `//` comments, **preserving newline count** so reported line numbers stay accurate) before the scan — same class as the `validate_gateway_tenancy.py` comment-strip; mirrors `check_connectivity_widget()`. **7/7 PASS**, no real site masked. (b) `validate_report_sender.py`'s `db_client` check grepped a literal `supabase.createClient` that report-sender.html no longer contains (it migrated to the canonical **`getDb()`** helper, supabase-js still in `<head>`); broadened to accept `getDb(` → **36/36 PASS** (a false FAIL retired — same "stale string-match" class).

**LIVE-PROVEN** (edge :54321, restarted to load the new `index.ts`; service-role bearer → skips tenancy; DB read via `docker exec psql` on `supabase_db_workhive`): a fresh transcript = **MISS 2.418s** (real LLM chain); the identical repeat = **HIT 0.091s** (~26× faster, no LLM call); `ai_cache` gained a `model='voice-action-router'` row with `hit_count` bumped; the edge log printed `[voice-action-router] router cache hit`. **Re-proven for `voice-report-intent`** after an edge restart: MISS **0.784s** → HIT **0.063s** (~12×), its own `ai_cache` row + `hit_count` bump + `[voice-report-intent] intent cache hit`. Synthetic test rows cleaned up. The **429-degrade** half of the Pillar-C proof ("cache-hit + 429-degrade observed live") was already shown in Pillar P (verified-tenant rate-limit). **The k6 binary is not installed locally → the rig stays dormant scaffolding** — but it is NOT "blocked on staging" (a prior misframe): `tools/load_test.k6.js` targets `http://127.0.0.1:54321`, so it runs against the LOCAL edge once `k6` is installed.

**Honest status:** Pillar C ~50% → ~62%, ⏳ in progress (NOT complete). Remaining: more cache adopters (next deterministic classifiers — correctness-gate each with the upstream-of-tenant test), per-route quota adoption beyond the front door, generalize circuit-break into reusable middleware *only if a real downstream-dependency gap surfaces* (not scaffolding), and install `k6` → run the LOCAL rig. **Files (LOCAL):** `voice-action-router/index.ts` + `voice-report-intent/index.ts` (cache wraps), `validate_resilience.py` (`_blank_comments`), `validate_report_sender.py` (getDb-aware `db_client`). Skills (Rule C): performance · ai-engineer · qa-tester · multitenant-engineer (cache-isolation) · devops.

---

## 7. DECISIONS

**RESOLVED 2026-06-15** (Ian: "ok now start" = accept the recommendation):
- **Fork 1 — Gateway scope = (c) Both, sequenced.** Front-door spine first, then the layer sweep folds on as middleware.
- **Fork 2 — Phase-1 lead = (a) R+I+P spine.** ✅ keystone landed.

_(original options preserved below for context)_

These genuinely change what gets built. **My recommendation in bold; tell me if you'd steer differently.**

**Fork 1 — what does "Gateway" mean?**
- **(a) Build the real front door first** ⭐*recommended* — architectural consolidation: the `_shared/gateway.ts` pipeline + server-side tenant context, adopted across 56 fns, then sweep the rest. Strongest read of "Gateway"; matches the SaaS-Lens control plane.
- (b) Layer-maturity sweep — no new front door; drive all 13 layers to "very good build" via the existing gate. Broader but flatter.
- (c) **Both, sequenced** ⭐*my overall pick* — front-door spine FIRST, then the layer sweep folds onto the pipeline as middleware. The full Companion-sized treatment; the §4 build order already assumes this.

**Fork 2 — which pillar leads Phase 1?**
- **(a) R+I+P — the Gateway Spine** ⭐*recommended* — the architectural centerpiece; C/O/DR then fold onto it as middleware instead of scattered per-function patches.
- (b) O — Observability & SLO — start with the weakest pillar; highest "proper SaaS" signal, lower blast radius, but best built *on* the pipeline (some rework if done first).
- (c) D — Foundation hardening — safest, but D is already 🟢 so marginal gain is small.

**My one-line recommendation:** *Fork 1 = (c) Both, sequenced; Fork 2 = (a) the R+I+P spine.* Decide these and we start Phase 1.

---

## 8. Sources & anchors

**Outside (reputable):**
- AWS Well-Architected SaaS Lens — control plane vs application plane · https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/the-pillars-of-the-well-architected-framework.html
- Backend-for-Frontend / API-Gateway pattern (Teleport) · https://goteleport.com/learn/cybersecurity-best-practices/backend-for-frontend-bff-pattern/
- 12-Factor App in 2025 + SRE/observability/SLOs · https://dev.to/whoffagents/the-12-factor-app-in-2025-what-still-applies-and-whats-changed-1nk0

**Internal (skills + memory consulted):** architect skill (DB-trust / `_shared` fan-out / hive-gate patterns), `COMPREHENSIVE_STUDY_FULLSTACK_GATE.md` §4 matrix, `AI_SURFACE_MAP.md §0.8` (the pillar template), `PLATFORM_ROADMAP.md` (per-layer honest %), `feedback_stay_local_dont_suggest_prod_push`.

---

## 9. Standing rules (inherited from the study §8 + local-first)

- **Rule A** — every production change lands with a gate change.
- **Rule B** — baselines only move down.
- **Rule C** — every fix updates ≥3 skills.
- **Rule L (local-first)** — build local-ready; prod deploy is Ian's call, never a pending action.

---

## Changelog

- **2026-06-15 (f)** — **Pillar R COMPLETE — auth_uid IDOR class FIXED + coverage enforced + LIVE-proven.** Generalize-then-fix: the identity-key family scan found 2 fns (voice-semantic-rag + agentic-rag-loop) scoping a voice-journal read by client `auth_uid`; fixed both (JWT-derived uid via `resolveIdentity`, body ignored, anon→empty; service-role forward keeps supplied uid) + `voice-handler.js` sends the user access token. Extended `validate_gateway_tenancy.py` to the identity-key family + comment-stripping (self-test 8/8, baseline 0). Un-deferred `validate_gateway_coverage.py` (uncovered 1→0, L3 WARN→FAIL, ALL 4 PASS). LIVE-proven (victim 11,933 entries): attacker→`unauthenticated` empty, authed→self-scoped, body uid ignored. Regression: agentic_rag 21/21, edge_contracts 0 FAIL. Pillar R now 🟢 ~75%. Gotcha logged: no-arg `getUser()` returns null on edge → use `getUser(jwt)`. Skills: security, ai-engineer, qa-tester. All LOCAL. NEXT: Phase 2 (C).
- **2026-06-15 (e)** — **Pillar R recon + routing triage + a real IDOR found.** Recon (§6e) showed the queued "envelope-body migration" is a trap/already-done (contract 🟢, consumers unwrap, errors deliberately flat for edge_contracts); the real R gap = routing coverage. Triaged `validate_gateway_coverage.py`'s 17 uncovered → **16 bypass-justified** (verified per-fn: self-secured structured tools / solo / internal / stateless), uncovered 17→1. The 17th, **voice-semantic-rag, is a per-user IDOR** (client-supplied `auth_uid` + service-role read of another worker's voice journal — the `auth_uid` analogue of the Pillar-I hive_id hole) → left UNCOVERED (no false-green), flagged in-code, ratchet kept DEFERRED. Fix = product fork (frontend sends user JWT; anon-companion impact). Skills: security, multitenant-engineer, architect, qa-tester. All LOCAL. NEXT: the voice-semantic-rag fix (Ian's call) then Phase 2 (C).
- **2026-06-15 (d)** — **Pillar P-PII: PII-egress ENFORCED (advisory→hard gate).** No prod code change — the gateway already centralizes redaction; the 2 `validate_pii_egress.py` L2 flags were both non-leaks (resume-extract = own-PII opt-in; agentic-rag-loop = false positive, token is DB-scoping/instruction not prompt data) → code-verified exempt (PII_EGRESS_OK 6→8). Promoted L2 **WARN→FAIL** (zero PII-to-LLM enforced); proved teeth via exemption-stripped in-process sim (2 hard-FAILs). Pillar P now 🟢 ~75%. Skills: security, ai-engineer, qa-tester, enterprise-compliance. §6d AS-BUILT. All LOCAL. NEXT: Pillar R (envelope-body, risky).
- **2026-06-15 (c)** — **Pillar P keystone: verified-tenant rate-limit binding + LIVE-proven.** Closed an unauthenticated cross-tenant DoS (anon-capable fns keyed rate-limit on the *client* `hive_id`): `ai-gateway` anon path now buckets on identity/IP, `resume-extract`/`resume-polish` always identity-bucket (dead local `checkAIRateLimit` removed; dropped from tenancy exempt 4→2). NEW `validate_policy_hive_binding.py` (G0 ratchet, registered, self-test 6/6, exploitable baseline 0; 8 latent authed call sites reported, not failed). LIVE-proven via `docker exec psql` on the edge's real DB (the postgres MCP was on a stale/empty DB): anon spoofed-hive → `hive_id=NULL` solo bucket, victim untouched; member path unchanged. tenancy validator 6/6 + PASS, auto-discovery 345 PASS. Skills: security, multitenant-engineer, architect, qa-tester (Rule C). See §6c AS-BUILT. All LOCAL. NEXT: Pillar R (envelope-body migration — risky) + P-PII adoption.
- **2026-06-15 (b)** — **Phase 1 keystone landed + LIVE-proven.** Forks resolved (both-sequenced; R+I+P spine). Discovery: the gateway front door already existed (`platform-gateway`) → harden, not build. Confirmed systemic tenancy hole (both front doors trusted client `hive_id`). Shipped `_shared/tenant-context.ts` (Pillar I), hardened `platform-gateway` (403 on foreign hive + trace-id; live-proven `auth_required`+`trace_id`), `validate_gateway_tenancy.py` (self-test 5/5, baseline 34, registered, auto-discovery green). Rollout backlog = 34→0; next = `ai-gateway`. See §6b AS-BUILT. Skills updated: security, multitenant-engineer, architect, qa-tester (Rule C). All LOCAL.
- **2026-06-15 (a)** — Roadmap created. Synthesis folded from the planning session: reframe (Gate ≠ Gateway), lead fusion verdict (distributed → one pipeline), 8 pillars with honest state, build order, 6 phases, 2 open forks (§7).
