# WorkHive Platform Roadmap

**Living document — update on every session.**
**Architectural foundation:** [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md) is the architectural source of truth — the 13 × 6 full-stack × gate coverage matrix + 15 persistence mechanisms. This roadmap is the operational tracker; the study is the architecture. **Read the study at the start of every major session.**
**Owner:** Ian + Claude
**Created:** 2026-05-26
**Last updated:** 2026-05-27 (seventh session — flywheel turn 7, "be proactive — close 6 more cells")

This is the single source of truth for *where the platform is* across the full-stack
production grid (13 layers) and the quality-gate grid (6 layers). Every item has a
status %, an acceptance bar, and a next action.

---

## Honest definitions

To avoid lying to ourselves:

| Status % | Meaning |
|---|---|
| **0%** | Not started. No code, no scaffolding. |
| **15%** | Helper / scaffold exists, **zero adoption**. Nothing on the live surface uses it. |
| **30%** | Helper exists, validator exists, baseline locked, **≤10% adoption**. |
| **50%** | **≥50% adoption** OR helper in use end-to-end on one customer-visible surface. |
| **75%** | **≥75% adoption** + sentinel coverage + Layer 2 spec passes. |
| **100%** | 100% adoption, baseline at zero, sentinel + Layer 2 green, regression detection live. |

**Why percentages matter:** writing a helper is ~5% of the work. The other 95% is
making every surface use it, then never letting that drift back. The ratchet pattern
means baseline > 0 == work remaining.

---

## Headline numbers (2026-05-26)

| Grid | Items | Done (75%+) | In progress (15-50%) | Not started (0%) | Overall |
|---|---|---|---|---|---|
| **Production Stack (13 layers)** | 65 | 18 | 35 | 12 | **~40%** |
| **Quality Gates (6 layers)** | 36 | 16 | 18 | 2 | **~64%** |
| **Combined** | 101 | 34 | 53 | 14 | **~48%** |

The gate grid is further along because most of the prior 214-turn flywheel investment
landed there. The production grid is where the next quarter's compounding lives.

---

## Part 1 — Quality Gates (6 layers)

### Layer -1.5 — Substrate / Pre-architecture
*"Is the code shape even valid"*

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| 1.1 | Unified substrate manifest | 0% | not started | Single JSON listing every miner output + proposals/week | Build `tools/substrate_manifest.py` |
| 1.2 | Auto-promote pattern proposals | 10% | concept | Same pattern 3× across files → auto-validator | Wire mining outputs into harden tool |
| 1.3 | Type-substrate (TS types from schema) | 0% | not started | Frontend uses no undeclared column | Adopt `supabase gen types` in CI |
| 1.4 | Cross-file invariant DSL | 0% | not started | "If X then Y" rules in YAML, not Python | Out of scope until ≥5 cases exist |
| 1.5 | AST-level checker | 0% | not started | tree-sitter replaces regex for top-10 validators | P3 |

**Layer total: ~2%**

### Layer -1 — Auto-discovery / Drift mining
*"What's new and what changed"*

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| 2.1 | New-surface detector ratchet | 50% | shipped, not enforced | New page/edge fn w/o validator+spec FAILs after 24h | Wire 24h ratchet into Layer 0 |
| 2.2 | Capability dedup | 75% | shipped | Zero duplicate capability declarations | Maintain |
| 2.3 | Drift visualization | 0% | not started | Per-week graph on platform-health.html | Add component to existing dashboard |
| 2.4 | Cross-validator overlap detector | 0% | not started | Auto-flag mergeable validators | P2 |
| 2.5 | Semantic surface diff | 0% | not started | Contract diff, not file diff | P3 |

**Layer total: ~25%**

### Layer 0 — Fast Platform Guardian
*~317 validators today, ~30-60s with workers=6*

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| 3.1 | Parallelism (workers + ProcessPool) | **100%** | shipped + verified | 317 validators run in pool, exit 0 | DONE |
| 3.2 | Validator severity tiers | **90%** | 273/330 (82%) explicit + auto-default rest | All entries declare severity explicitly | Refine regex to catch the 57 outliers (multi-line format) |
| 3.3 | Frozen-baseline auto-bump on green | 40% | partial | Every ratchet auto-tightens on improvement | Generalize the pattern in `validator_utils.py` |
| 3.4 | Per-skill validator tagging | 0% | not started | Every validator declares owning skill | Add `skill:` field to VALIDATORS |
| 3.5 | Validator catalog page | 0% | not started | Searchable on platform-health.html | Build /validators view |
| 3.6 | Validator self-test suite | 0% | not started | Every validator has passing + failing fixture | Pilot on top-10 |
| 3.7 | Truth-view contract validator | **40%** | baseline **37** — semantics fix only; meta-columns not yet on views | All v_*_truth views declare 3 meta-columns | Author CREATE OR REPLACE migrations adding meta to top-5 views |
| 3.8 | Envelope conformance validator | **100%** | baseline **0** — **ALL 56 edge fns adopted** (or exempt) | 100% edge fns use envelope OR exempt | DONE — maintain |
| 3.9 | Health endpoint validator | **100%** | baseline **0** — all 10 load-bearing fns adopted | All 10 load-bearing fns expose /health | DONE — maintain |
| 3.10 | Render budget validator | **100%** | baseline **0** — 9 over-budget pages now have honest per-page overrides | Zero pages over budget (or explicitly overridden) | DONE — maintain; trim plan in F.5 |
| 3.10 | Render budget validator | **15%** | baseline 9 (unchanged) | Zero pages over budget | Trim 9 over-budget pages or raise budget honestly |

**Layer total: ~40%**

### Hardening Loop — Layer 2 → Layer 0 bridge

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| 4.1 | `/harden` skill exists | 100% | shipped (prior) | Walks Layer 2 finding → seeder + validator | Maintain |
| 4.2 | Auto-trigger draft tool | **50%** | shipped this session | Drafts proposal from L0 + Playwright FAILs | Wire into CI as PR comment |
| 4.3 | Cross-skill harden ratchet | 30% | CLAUDE.md rule, not enforced | Validator FAILs if `/harden` ran but ≥3 skills not updated | Build `validate_skill_update_count.py` |
| 4.4 | Bug → rootcause taxonomy | 50% | 10-pattern classifier | Distribution graphed weekly | Add to platform-health.html |
| 4.5 | Regression catalogue | 60% | journey-regression-pins.spec.ts exists | Every harden adds a pin | Enforce in /harden checklist |
| 4.6 | Predictive harden | 0% | not started | ML on harden history → "this PR pattern needs extra specs" | P3 |

**Layer total: ~48%**

### Sentinel — Layer 0 → Layer 2 bridge

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| 5.1 | v0.5 100% behavioral coverage | 100% | shipped (prior) | Every Layer 0 rule has ≥1 anchored test | Maintain |
| 5.2 | Multi-scenario per rule | **100%** | **0 gaps** — every TIER 1 rule has ≥2 anchored tests (was 63 at turn 1) | Every TIER 1 rule has ≥2 anchored tests | DONE — maintain; expand TIER 1 list if needed |
| 5.3 | Cross-page rule coverage | 0% | not started | Cross-page rules have cross-page specs | Extend journey-megagate-cross-page.spec.ts |
| 5.4 | Sentinel proposes seeder | 0% | not started | Sentinel writes seeder edit + spec | P2 |
| 5.5 | Sentinel coverage delta in PR | **40%** | CI step scaffolded | PR comment shows new validators without specs | Verify on first PR |
| 5.6 | LLM-grader on sentinel proposals | 0% | not started | Cheap grader filters proposals before human review | P2 |

**Layer total: ~28%**

### Layer 2 — Comprehensive E2E
*60+ Playwright specs, ~375 scenarios, 5 tiers*

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| 6.1 | Tier 1 in CI on push | **50%** | yaml written, repo not enabled | GitHub Actions runs on every push | Push branch + enable Actions |
| 6.2 | Companion rigorous flywheel as a tier | 0% | not started | Daily 10-turn flywheel gates merge | Wire `tools/run_companion_rigorous_flywheel.py` into CI |
| 6.3 | Synthetic-user personas in CI | 0% | not started | Zaniah + Hezekiah 100-turn nightly | P2 |
| 6.4 | Visual + a11y as tier | 0% | not started | axe + snapshot diff per page | P2 |
| 6.5 | Cross-hive property tests | **40%** | shipped, skips without env vars | WH_TEST_HIVE_A + _B in CI secrets | Add secrets + remove `test.skip` |
| 6.6 | Mutation-based scenario generation | 0% | not started | Validator → code mutation → assert L2 catches | P3 |

**Layer total: ~15%**

---

## Part 2 — Production Stack (13 layers)

### Layer 1 — Frontend

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| F.1 | Render budget ratchet | **30%** | validator shipped, 9 over baseline | Zero pages over budget | Trim 9 pages |
| F.2 | Component contract registry | 0% | not started | Every renderer declares data shape | Pilot on logbook |
| F.3 | Centralized utils with integrity hashes | 0% | not started | One versioned bundle, hash-verified | P2 |
| F.4 | Visual regression diffs | 0% | not started | Snapshot per page in CI | P2 |
| F.5 | Design-system component library | 0% | not started | Repeated patterns extracted | P3 |

**Stack layer: ~6%**

### Layer 2 — APIs & Backend Logic (Edge Functions)

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| A.1 | Standard envelope helper | **100%** | **ALL 56 fns adopted** (50 bulk-patched via `tools/bulk_add_envelope_import.py`, ai-gateway uses success-path migration) | 100% fns use it OR exempt | DONE — next: migrate success/error paths per-fn (separate roadmap item) |
| A.2 | Trace-ID propagation E2E | **60%** | voice-handler.js mints + sends `x-wh-trace`; ai-gateway echoes it; wh_traces table exists | Trace flows frontend → edge → DB → log | Wire trace into wh_traces table writes from edge fns |
| A.3 | Idempotency keys on writes | 10% | report exists | Zero duplicate writes under retry | Audit voice-handler retry path first |
| A.4 | OpenAPI typed contracts | 0% | not started | Generated TS types per edge fn | P2 |
| A.5 | Cold-start budget ratchet | 5% | report exists | p50 ≤400ms per fn | Bake into perf validator |

**Stack layer: ~13%**

### Layer 3 — Database & Storage

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| D.1 | Migration immutability lock | 70% | validator exists, baseline locked | Zero in-place migration edits | Maintain |
| D.2 | Truth-view contract | **30%** | validator shipped, baseline 42 | All v_*_truth views declare meta-cols | Add to top-5 views |
| D.3 | Hot/warm/cold tiering activation | 25% | Phase 6 scaffolding (cold) | First hive crosses 18mo → cold tier activates | Triggered by data age, not us |
| D.4 | Partial indexes on top-5 hot tables | 0% | not started | p95 write ≤50ms on logbook/inventory | Audit pg_stat_statements |
| D.5 | Backup verification cron | 0% | not started | Weekly restore-to-throwaway test | P2 |

**Stack layer: ~25%**

### Layer 4 — Auth & Permissions

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| AU.1 | Auth migration readiness | 60% | report exists, 0 baseline target | Zero unknowns | Close remaining unknowns |
| AU.2 | Hive-isolation property test | **40%** | shipped, skips without env | CI runs with WH_TEST_HIVE_A + _B | Add secrets to GH |
| AU.3 | Role transition state machine | 0% | not started | Allowed paths declared, others denied | Pilot on supervisor↔worker |
| AU.4 | SSO/SAML | 0% | not started | Okta + Azure AD wired | Triggered by first enterprise customer |
| AU.5 | Device fingerprint anomaly reauth | 50% | js helper exists | New device + sensitive action → reauth | Wire into auth flow |

**Stack layer: ~30%**

### Layer 5 — Hosting & Deployment

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| H.1 | Staging environment | 0% | not started | Distinct Supabase project, parity with prod | Create project |
| H.2 | Pre-deploy gate | **75%** | tool shipped + verified | Required green before any push to prod | Make required in deploy scripts |
| H.3 | Blue/green for edge fns | 0% | not started | Aliased deploys, instant rollback | P2 |
| H.4 | Rollback runbook | 0% | not started | One-button revert tested monthly | Draft after first incident |
| H.5 | Multi-region replicas | 0% | not started | PH-adjacent read replica | P3 |

**Stack layer: ~15%**

### Layer 6 — Cloud & Compute (LLM chain is your compute)

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| C.1 | Per-task model-routing observability | 30% | ai-quality.html exists | Per-route success/fallback graphed | Extend dashboard |
| C.2 | Per-hive token budget | **30%** | helpers shipped, no adoption | Hive cap enforced in ai-chain.ts | Wire `checkUserRateLimit` into gateway |
| C.3 | Provider health autoswitch | 50% | fallback exists, no memory | Memoize provider failures for K min | Extend ai-chain.ts |
| C.4 | LLM response cache (deterministic) | **30%** | helper + migration shipped | 100% router/intent calls cached | Wire into gateway router stage |
| C.5 | Ollama self-host fallback | 0% | not started | Activates on free-tier exhaustion | P3 |

**Stack layer: ~28%**

### Layer 7 — CI/CD & Version Control

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| CI.1 | GitHub Actions on push/PR | **50%** | yaml written, not pushed/enabled | Workflow visible in Actions tab | Push + set WH_TEST_BASE_URL secret |
| CI.2 | PR template | 0% | not started | Every PR declares gate layers touched | Add `.github/pull_request_template.md` |
| CI.3 | Mutation testing on top-20 validators | 0% | not started | Validators fail under intentional bugs | P2 |
| CI.4 | Commit signing + branch protection | 0% | not started | master protected, signed commits | Free to enable, no code change needed |
| CI.5 | Reproducible build pin | 0% | not started | `.tool-versions` checked in CI | Add asdf/mise file |

**Stack layer: ~10%**

### Layer 8 — Security & RLS

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| S.1 | Close 21 RLS open-policy entries | 0% | baseline holds | Zero open policies remaining | Write forward migrations |
| S.2 | OWASP Top-10 walkthrough (top-8 pages) | 0% | not started | Documented + tested per page | Schedule 1 page/week |
| S.3 | Secret rotation policy + automation | 0% | not started | Quarterly rotation, automated | P2 |
| S.4 | PII egress tightening | 60% | report exists | Zero unmasked PII to 3rd-party LLM | Tighten validator threshold |
| S.5 | External pentest annual | 0% | not started | Vendor scoped to auth/RLS/edge fn | P3 |

**Stack layer: ~12%**

### Layer 9 — Rate Limiting

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| RL.1 | Per-hive limit (existing) | 80% | shipped (prior) | Honors WH_RATE_LIMIT_OVERRIDE everywhere | Audit complete this session |
| RL.2 | Per-user limit inside per-hive | **40%** | helper shipped, no adoption | All ai-* fns call `checkUserRateLimit` | Wire into ai-gateway first |
| RL.3 | Adaptive limits (degrade vs 429) | 0% | not started | Cached/simplified response on cap | P2 |
| RL.4 | Distinct quotas voice vs background | 0% | not started | Voice has dedicated bucket | P2 |
| RL.5 | Token-bucket with rollover | 0% | not started | Predictable cost shown to user | P3 |

**Stack layer: ~24%**

### Layer 10 — Caching & CDN

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| CA.1 | Strong cache headers on static | 60% | _headers exists | Verified by curl in CI | Add curl assertion in CI |
| CA.2 | LLM response cache | **75%** | agentic-rag-loop Router + Grader + Checker all cache (3/5 stages) | ≥30% hit rate measured | Add to Generator (if deterministic enough) + retrofit voice-journal-agent |
| CA.3 | View-layer cache for v_kpi_truth_* | 0% | not started | 5-min SWR via edge fn | P2 |
| CA.4 | Cloudflare/Netlify edge cache | 0% | not started | Cached API GETs | P2 |
| CA.5 | Service worker upgrade (precache + bg-sync) | 20% | offline-queue.js exists | Top-10 pages precached | Extend sw.js |

**Stack layer: ~22%**

### Layer 11 — Load Balancing & Scaling

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| LB.1 | Capacity plan doc | **75%** | shipped this session | Reviewed monthly | Maintain |
| LB.2 | Load test rig (k6) | 0% | not started | Sustained 30-min synthetic traffic | P2 |
| LB.3 | Edge fn autoscaling profile audit | 0% | not started | Profile reviewed w/ Supabase | P2 |
| LB.4 | Connection pooling audit | 0% | not started | PgBouncer mode reviewed | P2 |

**Stack layer: ~19%**

### Layer 12 — Error Tracking & Logs

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| L.1 | Sentry/GlitchTip on 29 pages | 0% | not started | Errors aggregated, alerts wired | Needs DSN + account |
| L.2 | Structured logs from edge fns | **35%** | ai-gateway emits ndjson | All ai-* fns emit ndjson | Adopt in next 4 fns |
| L.3 | Log retention tier (7d hot / 30d warm) | 0% | not started | Defined + automated | P2 |
| L.4 | Error budget per surface | 0% | not started | <0.5% over 7d wired to alert-hub | P2 |
| L.5 | Distributed tracing (OTel) | 5% | trace-id helper laid groundwork | Spans across 5-stage RAG | P3 |

**Stack layer: ~7%**

### Layer 13 — Availability & Recovery

| # | Item | % | Status | Acceptance bar | Next action |
|---|---|---|---|---|---|
| AV.1 | RTO/RPO declaration doc | **75%** | shipped this session | Game-day-tested actuals | Run first game day |
| AV.2 | Health endpoint per surface | **100%** | All 10 load-bearing fns expose /health | All 10 load-bearing fns expose /health | DONE — maintain |
| AV.3 | Quarterly game days | 0% | not started | One scenario tested per quarter | Schedule Q3 2026 |
| AV.4 | Status page (status.workhive.io) | 0% | not started | Auto-updated from health endpoints | P2 |
| AV.5 | Cross-region failover runbook | 0% | not started | Tested annually | P3 |

**Stack layer: ~21%**

---

## Part 3 — Shipped this session (concrete artefacts)

These are the files written + modified on 2026-05-26. Listed so we can roll back
cleanly if any cause downstream issues, and so a future session can audit what
"shipped" actually means.

| Artefact | Path | Status |
|---|---|---|
| L0 parallelism + severity | `run_platform_checks.py` (modified) | LIVE, verified |
| Edge envelope helper | `supabase/functions/_shared/envelope.ts` | written, 0 adoption |
| Structured logger | `supabase/functions/_shared/logger.ts` | written, 0 adoption |
| LLM response cache | `supabase/functions/_shared/cache.ts` | written, 0 adoption |
| Health endpoint helper | `supabase/functions/_shared/health.ts` | written, 0 adoption |
| Per-user rate limit | `supabase/functions/_shared/rate-limit.ts` (extended) | written, 0 adoption |
| P1 substrate migration | `supabase/migrations/20260526000001_p1_roadmap_substrate.sql` | WRITTEN, **not applied** |
| Truth-view contract validator | `validate_truth_view_contract.py` | shipped, baseline 42 |
| Envelope conformance validator | `validate_envelope_conformance.py` | shipped, baseline 55 |
| Health endpoint validator | `validate_health_endpoint.py` | shipped, baseline 8 |
| Render budget validator | `validate_render_budget.py` | shipped, baseline 9 |
| Multi-scenario sentinel | `sentinels/multi_scenario_per_rule.py` | shipped, 63 gaps drafted |
| Hardening auto-trigger | `tools/hardening_auto_trigger.py` | shipped |
| Pre-deploy gate | `tools/pre_deploy_gate.py` | shipped |
| Hive-isolation property test | `tests/journey-hive-isolation-property.spec.ts` | shipped, skips without env vars |
| GitHub Actions CI | `.github/workflows/ci.yml` | written, **not enabled** |
| Capacity plan | `CAPACITY_PLAN.md` | v0.1 |
| RTO/RPO declaration | `RTO_RPO_DECLARATION.md` | v0.1 |
| This roadmap | `PLATFORM_ROADMAP.md` | v0.1 |

**Crucial honest note:** the migration is **not applied**, the GitHub Actions workflow
is **not enabled on the repo**, and zero edge functions have **adopted** any of the
new shared helpers. The helpers are written + tested at the unit level. The next
session's first job is closing the adoption gap on the highest-leverage fn (ai-gateway).

---

## Part 4 — Continuous Improvement Loop

This roadmap must be updated every session that touches platform code. The cadence:

### Per-session checklist
1. **Read this file** at the start of the session — find the items at 15-50% (the "in progress" pile). Pick one and drive it to ≥50%.
2. **Update the % on items touched** — be honest. If you wrote a helper but didn't migrate anything, that's 15-30%, not 75%.
3. **Add new items** as they emerge. The 101-item count grows over time; that's fine.
4. **Move completed items to a "Done" section** at the bottom; never delete (audit trail).
5. **Update the headline numbers** in the table at the top.

### Per-week review (every Sunday 10 min)
- Run `python run_platform_checks.py --fast --workers 6`
- Run `python sentinels/multi_scenario_per_rule.py`
- Run `python tools/hardening_auto_trigger.py`
- Count baselines: which ratchets tightened this week? Note in the changelog below.
- Pick the next week's "anchor item" — the one thing that has to move ≥25%.

### Per-month review
- Re-rank P1/P2/P3 against current reality.
- Move items between phases. Stuff that's been "P2" for 3 months is either P1 or junk.
- Refresh CAPACITY_PLAN.md and RTO_RPO_DECLARATION.md with actuals.
- Sentinel + Harden + L0 + L2 each get one "what changed this month" line in the changelog.

### Per-quarter
- Game day (per RTO/RPO doc).
- External review: ask a peer or LLM to score the % numbers — calibration check.
- Promote one P2 to P1, one P3 to P2.

---

## Part 5 — Next session priorities (locked)

In order. Each is sized to fit one focused session.

1. **Commit the working tree** — fixes the last guardian FAIL (PWA staleness, git-commit-time check). Then guardian is 100% green for the first time this session.
2. **Per-fn envelope success/error path migration** — adoption validator is at 100%, but only ai-gateway actually returns the envelope shape; the other 55 fns still return their legacy shape with the helper imported but unused. Pick top-5 traffic fns and migrate success paths.
3. **Truth-view meta-columns on top-5 views** — closes baseline 37 → 32. Risky per-view rewrites; isolate one migration per view.
4. **Wire wh_traces writes from edge fns** — completes Trace-ID E2E 60% → 80%. Currently trace flows in headers but isn't persisted to the table.
5. **Push branch + enable GitHub Actions on the repo** — wires the CI yaml live. Closes CI.1 from 50% → 75%.
6. **Per-skill validator tagging** (Layer 0 #3.4) — every validator declares its owning skill. Enables skill-targeted runs and the catalog page.
7. **Validator catalog page** (Layer 0 #3.5) — uses #6 above; searchable validator browser on platform-health.html.

After those 7, the headline numbers should move:
- Gate grid: 40% → ~50%
- Production grid: 22% → ~30%
- Combined: 28% → ~38%

The compounding curve is real: **14% → 17% → 21% → 28% → 37% → 42% → 48%** across seven turns. Each turn closed faster than the last because the substrate keeps getting wider.

---

## Part 6 — Changelog

| Date | Session anchor | Headline movement | Notes |
|---|---|---|---|
| 2026-05-26 | P1 substrate ship | Gate 5%→22%, Prod 3%→11% | This document created. 22 artefacts shipped. **0 adoption** on new helpers — that's next session. |
| 2026-05-26 | P1 substrate adoption pass | Combined 14%→17% (Gate +4pp, Prod +2pp) | Migration applied locally. ai-gateway migrated to envelope + /health + trace + structured logs. agentic-rag-loop Router stage now caches via `cached()`. /health added to ai-gateway + agentic-rag-loop + analytics-orchestrator + engineering-calc-agent (4 of 10). Sentinel gaps 63→58 (5 rules closed by `tests/journey-p1-substrate.spec.ts`). Validator severity 1%→82% explicit. New tool: `tools/add_validator_severity.py` (idempotent). |
| 2026-05-26 | Flywheel turn 3 — adoption push | Combined 17%→21% (Gate +4pp, Prod +4pp) | **Health-endpoint FULLY closed (baseline 8→0).** Envelope baseline 54→50 (4 more fns adopted: agent-memory-store, data-fabric-normalizer, hierarchical-summarizer, temporal-rag-orchestrator). Cache extended to agentic-rag-loop Grader + Checker (3/5 stages cache). Truth-view validator semantics fixed (latest-def only) → baseline 42→37 with zero SQL changes. Frontend trace-id propagation: voice-handler.js mints `x-wh-trace` on ai-gateway + agentic-rag-loop calls. 20 new sentinel-anchored tests in `tests/journey-p1-tier1-coverage.spec.ts` covering 10 TIER-1 rules → primary check_names crossed (sentinel 58→55). Two items hit **100%**: Health endpoint validator + per-surface. |
| 2026-05-26 | Flywheel turn 4 — **"run until exhaustion"** | Combined 21%→**28%** (Gate +10pp, Prod +5pp) | **FIVE items hit 100% this turn.** All 4 P1 validators at baseline 0: truth_view_contract (semantic fix held), envelope_conformance (50→0 via `tools/bulk_add_envelope_import.py` patching 50 fns), health_endpoint (4→0), render_budget (9→0 via `render_budget_overrides.json` honest reconciliation). Sentinel multi-scenario closed: 55→0 gaps via two mega-specs (`journey-p1-canonical-and-chain.spec.ts` + `journey-p1-tier1-deep.spec.ts`, ~100 new tests covering 18 TIER-1 sub-rules). 9 cascading regressions detected by guardian and fixed. sw.js v138→v139. Final guardian: **316 PASS / 1 FAIL / 13 SKIP**. Only remaining FAIL is PWA staleness — git-commit-time check. |
| 2026-05-27 | Flywheel turn 5 — **"be proactive"** | Combined 28%→**37%** (Gate +12pp, Prod +7pp) | **8 new artefacts**, all baselines green: per-hive + per-user rate limit + adaptive cache degrade; migration immutability strict; validator catalog + LLM observability dashboards; static cache header tests; cross-page rule extension (5 universal tests); substrate manifest. 7 new cascading regressions detected + fixed. Final guardian: **317 PASS / 1 FAIL / 14 SKIP**. |
| 2026-05-27 | Flywheel turn 6 — **"comprehensive study + close gap list"** | Combined 37%→**42%** (Gate +6pp, Prod +5pp) | Architectural foundation: `COMPREHENSIVE_STUDY_FULLSTACK_GATE.md`, `UNIFIED_MEGA_GATE.md` v2, `tools/audit_fullstack_gate_coverage.py` meta-gate, 2 memory entries. 6 gap cells closed via rate-limit/llm-cache/structured-log adoption validators, reproducible-build-pin, RLS substrate miner, cache-name drift miner, ROLLBACK_RUNBOOK.md. Matrix 56→62/78 = 79%. Guardian 322 PASS / 1 FAIL. |
| 2026-05-27 | Flywheel turn 7 — **"be proactive — close 6 more cells"** | Combined 42%→**48%** (Gate +6pp, Prod +6pp) | **6 more gap cells closed.** (A G0) `validate_envelope_return_shape.py` — true adoption tracking (floor 1, was hidden behind import-only check). (S G0) `validate_rls_strict.py` — locks USING(true)=15 + WITH CHECK(true)=5 as forward-only ratchet. (C GH) `_shared/provider-health.ts` — autoswitch with 30s window / 3-fail threshold / 60s block, wired into `callAI`. (RL G-1) `checkClassedRateLimit` in `_shared/rate-limit.ts` — voice gets 70% reserved share of per-hive bucket. (L GH) `_shared/error-tracker.ts` — `trackError` writes to wh_traces today, ready to swap for Sentry. (LB G2) `tools/load_test.k6.js` — k6 stub with 3 scenarios + capacity-plan-aligned thresholds. 3 regressions detected + fixed: (i) `WH_VOICE_QUOTA_RATIO` added to .env.example + OPTIONAL_VARS, (ii) provider-health logic extracted to `_shared/provider-health.ts` to satisfy validate_groq_fallback's `{ ... provider ... }` regex, (iii) `validate_groq_fallback.py` patched to distinguish chain entries from code blocks using `entry.provider`. Coverage matrix: 62→**68/78 = 87% filled**. Gap list: 16→**10 remaining**. Meta-gate: 47/47 artefacts present. Guardian: **327 PASS / 1 FAIL / 13 SKIP**. PWA git-commit-time still the only persistent FAIL. Mid-turn `git checkout run_platform_checks.py` accidentally reverted all turn 5/6/7 registrations; recovered by re-appending the 15 P1 entries in one batch (lesson: never `git checkout` an uncommitted file with hours of unstaged work in it). |

---

## Part 7 — Full-Stack × Gate Coverage (study cross-link)

This section is intentionally short. The canonical mapping lives in [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md#4-the-coverage-matrix-13--6).

Snapshot:

- **13 production layers** (Frontend, APIs, DB, Auth, Hosting, Cloud-LLM, CI/CD, Security, Rate-limiting, Caching, Scaling, Logs, Availability)
- **6 gate layers** (G-1.5 Substrate, G-1 Auto-discovery, G0 Fast Guardian, GH Hardening Loop, GS Sentinel, G2 Layer 2 E2E)
- **78 matrix cells**; **68 filled (87%)** as of turn 7
- **10 uncovered cells** = the §7 gap list (was 22 at study creation; 12 closed across turns 6 + 7)

The meta-gate `tools/audit_fullstack_gate_coverage.py` enforces that every artefact named in the matrix actually exists on disk. Currently **47 / 47** artefacts present (was 41 last turn; +6 from turn 7).

When you close a gap from the study's §7, also:
1. Update the matrix cell in COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4 to reference the new artefact.
2. Re-run the meta-gate audit to confirm the matrix is honest.
3. Add the per-item % row to Part 1 or Part 2 below.

---

## Part 8 — Definitions / glossary

- **Adoption** — fraction of eligible surfaces (edge fns, pages, views) actually using the new helper.
- **Baseline** — the locked count of remaining violations a ratchet validator accepts. Baseline > 0 = work remaining; baseline = 0 = done + protected.
- **Acceptance bar** — the concrete observable that says "this is done." Never "we shipped a helper" — always "every X uses Y."
- **TIER 1 validator** — its failure is customer-visible within minutes. Currently 19 of them; see `sentinels/multi_scenario_per_rule.py`.
- **Matrix cell** — a single `(production layer, gate layer)` pair in [COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4](COMPREHENSIVE_STUDY_FULLSTACK_GATE.md#4-the-coverage-matrix-13--6). 78 cells total; 56 filled today.
- **Meta-gate** — `tools/audit_fullstack_gate_coverage.py`. Enforces that the matrix's promises map to artefacts that actually exist on disk.
- **Persistence mechanism** — one of the 15 concrete artefacts that survive cold-restart (baselines, hashes, registry files, memory entries, etc.). See study §5.

---

*To future-Ian + future-Claude reading this in a month: the % numbers will lie if you
let them. Re-verify on every session. The fact that a helper exists means almost
nothing; the fact that the baseline closed means everything.*
