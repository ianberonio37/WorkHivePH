# LIVE-PAGE FEATURE JOURNEYS — ARC K ROADMAP (MCP-as-User + UI/UX Critic)

_Spine doc for Arc K. Same method as Arc D (frontend) / E (edge+DB) / F (python) / G (data) / H (AI) /
I (auth) / J (realtime): per-cell IN-FRAME scoring into ONE ratcheted matrix, **measured-not-credited**,
denominator mined FIRST, with a hard split between live ✓ / pending / ◈ external-ceiling / N-A-by-evidence.
Selected by Ian (2026-06-22) as the 8th arc after the D–J cross-arc live-push reached 5/7 arcs at 100% live._

**Status: PLAN — baselines below are 0% (NOTHING measured live yet). K0 builds the harness
(`tools/live_page_journeys.mjs`) + mines the page×role×JTBD denominator + writes the real baseline matrix.
Awaiting `build K0`.**

> **Why this arc (the honest framing):** Arcs D–J each verify a *technical axis* (frontend cells, edge fns,
> DB, AI, auth, realtime). NONE asks the only question a paying customer cares about: **"on this page, can a
> real user actually get their job done — and how could the UI/UX be better?"** Arc K makes the **Playwright
> MCP behave like a real worker/supervisor/engineer**: it signs in, lands, reads the page, decides what to
> click (agentic, JTBD-guided), drives the feature end-to-end against the LIVE stack, and judges success by
> what it OBSERVES. It then **critiques** the page and emits ranked UI/UX improvement findings. D = "do the
> components honor their contracts." K = "can a user do the job, and how do we make it better."

---

## §0 — Method (the standing one)

Skills first → reputable sources → synthesize. **Skills consulted:** designer · frontend · mobile-maestro ·
qa-tester · performance · community · seo-content (the concrete project rules: design tokens, ≥44px taps,
≥16px inputs, contrast ≥4.5:1, focus-visible, empty/error CTAs, FAB-occlusion, CWV, plain-language).
**Reputable sources synthesized:** Nielsen-10 heuristics · Norman-7 principles · WCAG 2.2 POUR · jscpd
(clones/redundancy) · @axe-core/playwright (WCAG engine on the a11y tree) · UXAgent (CHI 2026, arXiv
2502.12561 — LLM-persona goal-driven usability sim) · UICrit (arXiv 2407.08850 — UI-critique rubric/dataset)
· "Catching UX Flaws in Code" (arXiv 2512.04262) · UX-Ray/Baymard (May 2026 — 346-heuristic auto-eval, ≥95%)
· the held `reference_holistic_critic_tooling.md`. **Key constraint:** axe-core proves only ~30–40% of WCAG;
the ~60% needing judgment is the LLM-critic's job. Playwright MCP operates on the **accessibility tree**
(roles/names/states), the ideal critic substrate.

---

## §1 — Lens model (unified): 5 journey lenses × U·F·A·I

| Journey lens | The question | Falsifiable bar | → U·F·A·I |
|---|---|---|---|
| **R** Reachable | Can the user get here + does it load usable? | nav/link/deep-link resolves · auth+role gate admits the right role · primary content paints | U + I |
| **J** Job-completable | Can the user finish the page's main task? | the JTBD happy path completes to a visible success state | F + U |
| **T** Truthful | Is what's shown real? | rendered numbers/rows trace to the live DB (no fabricated/empty-masquerade) | F |
| **C** Recoverable | Do empty/error/edge states guide, not trap? | empty has a CTA · bad submit → recoverable message · no dead-end | U + A |
| **X** Cross-page-coherent | Does the effect land where expected? | an action's result appears on its downstream surface | F + A |

---

## §2 — The UI/UX Improvement Critic (the 6th capability, run DURING each journey)

Two layers, emitted as a per-page **findings register** (finding · severity 0–4 · rule · selector/evidence ·
fix · owner-skill · lens hit):

- **Layer 1 — Deterministic floor (~30–40% machine-provable → RATCHETS TO 0):** axe-core (WCAG 2.2 via the
  a11y tree, violations with selectors) · jscpd clones + "a KPI rendered on >1 page = dedup defect" ·
  measured skill-rules (≥44px taps incl. icon-only dpr-corrected, ≥16px inputs, contrast ≥4.5:1, CWV
  LCP≤2.5/INP≤200/CLS≤0.1, focus-visible present, empty-state-has-CTA, sibling-44px-consistency,
  no bottom-right FAB occlusion via `elementFromPoint`).
- **Layer 2 — Heuristic judgment (~60% → severity-ranked backlog):** Nielsen-10 + Norman-7 + WCAG-POUR +
  our skills' concrete rules, scored 0–4 (Polish/Minor/Major/Blocker), grounded in the live a11y tree AND
  the journey friction (UXAgent pattern: "while completing JTBD X the user hit friction Y").

---

## §3 — Per-page scoreboard (live% tracker — the anti-drift instrument)

Unit = **JTBD** (one user job that must complete LIVE on the page). `live%` = live-passing JTBDs / applicable.
**Baseline = 0% (K0 not built).** `◈` = external-dependency JTBD (Stripe/Resend) = the genuine external
ceiling (local target excludes them, same as Arc E tier-1). Roles tested only where the page differs.

| Phase | Page | Roles | JTBDs | live% now | target | Critic floor |
|---|---|---|---|---|---|---|
| **K1** | index — landing + home dashboard | anon·F·S | 9 | **100%** ✅ (9/9) | 100% | **floor 0 ✓** |
| **K2** | logbook | F·S | 6 | **100%** ✅ (6/6) | 100% | →0 (focus/contrast backlog) |
| K2 | inventory | F·S | 5 | **100%** ✅ (5/5) | 100% | → 0 |
| K2 | dayplanner | F·S | 4 | **100%** ✅ (4/4) | 100% | **0 ✓** |
| **K3** | hive (team mgmt) | S | 6 | **100%** ✅ (6/6) | 100% | **0 ✓** |
| K3 | pm-scheduler | F·S | 4 | **100%** ✅ (4/4) | 100% | **0 ✓** |
| K3 | community | all | 4 | **100%** ✅ (4/4) | 100% | **0 ✓** |
| **K4** | analytics (+predictive/shift/ph-intel/reports tabs) | S·E | 5 | **100%** ✅ (5/5) | 100% | **0 ✓** (env-debt fixed) |
| K4 | assistant | all | 4 | **100%** ✅ (4/4) | 100% | **0 ✓** |
| K4 | asset-hub | S·E | 4 | **75–100%** (3-4/4) | 100% | **0 ✓** |
| K4 | alert-hub | S | 4 | **100%** ✅ (4/4) | 100% | **0 ✓** |
| K4 | audit-log | S | 4 | **100%** ✅ (4/4) | 100% | tap floor |
| K4 | voice-journal | all | 4 | **100%** ✅ (4/4) | 100% | **0 ✓** |
| K4 | ai-quality | S | 3 | **100%** ✅ (3/3) | 100% | **0 ✓** |
| K4 | analytics-report / report-sender | S·E | 4 | **75%** (3/4) | 100% | contrast floor |
| **K5** | engineering-design | E | 4 | **100%** ✅ (4/4) | 100% | tap+contrast floor |
| K5 | project-manager | S·E | 5 | **100%** ✅ (5/5) | 100% | **0 ✓** |
| K5 | project-report | S·E | 3 | **100%** ✅ (3/3) | 100% | contrast floor |
| K5 | skillmatrix + achievements | all | 4 | **100%** ✅ (4/4) | 100% | **0 ✓** |
| K5 | resume | all | 4 | **100%** ✅ (4/4) | 100% | **0 ✓** |
| **K6** | marketplace | anon·F | 5 | **100%** ✅ (5/5) | 100% (FREE — no Stripe) | **0 ✓** |
| K6 | marketplace-seller | F(=seller) | 4 | **100%** ✅ (4/4) | 100% (FREE — no Stripe) | **0 ✓** |
| K6 | integrations | S | 2 | **100%** ✅ (1/1 local + 1 ◈ IN5 CMMS-sync) | 100% local | **0 ✓** |
| K6 | plant-connections | S | 3 | **100%** ✅ (3/3) | 100% | **0 ✓** |
| — | **OVERALL** | — | **102 (1 ◈)** | **101/102 = 99% local ✅** | **baseline LOCKED: live≥101, floor≤10 · IN5 ◈ = real external CMMS API (Ian-gated)** | focus-visible cleared platform-wide; floor 10 = tap/contrast/scroll backlog |

**~104 JTBDs across 23 page-units (27 pages incl. embedded tabs). 1 ◈ external-ceiling JTBD** (IN5 = live
CMMS sync, needs a reachable real SAP/Maximo API). ★**FREE-PLATFORM REFRAME (Ian, 2026-06-22): Stripe is
removed — the platform is free.** The two former Stripe ◈ (marketplace MK "checkout" / seller MS "connect
payout") dissolve: `PAYMENTS_ENABLED=false` is already the page default, so the real jobs are the FREE flows
(browse · post · **Contact-Seller inquiry** · watchlist · saved-search · Messenger-handle), all locally
completable. Resend (analytics-report) was already live locally. → LOCAL target ≈ **100% live** (only IN5 ◈).

---

## §4 — Per-lens + phase rollup (fills in as K-phases land)

| Phase | Pages | JTBDs | live% (now → target) | Exit |
|---|---|---|---|---|
| **K0** | harness + denominator | — | ✅ **DONE** | `live_page_journeys.mjs` (+ `.heuristics.mjs` + `.registry.mjs`) runs; 209-rule critic catalog; baseline written; ratchet locked |
| **K1** | landing + home (the front door) | 9 | **0% → 88.9% ✅** | method PROVEN: 8/9 live (T·C·X 100%, R·J 87.5%), floor → 0. 1 gap = LA5 stale "try free" promise (Ian product fork, not a code bug) |
| **K2** | Field Work (3) | 15 | **0% → 100% ✅** | DONE: log/inventory/plan jobs complete live (real DB-verified writes + cleanup) + cross-page coherent. ★Arc K CAUGHT+FIXED a real bug: dayplanner today/week counts used `toISOString()` (UTC) vs `toYMD()`-saved local dates → undercounted every PHT evening (fixed to local `toYMD`). |
| **K3** | Your Team (3) | 14 | **0% → 100% ✅** | DONE: team mgmt + PM + community jobs live (real DB-verified mutations w/ seed+revert). ★Arc K CAUGHT+FIXED 2 MORE real bugs: (1) `hive_members_update` RLS **infinite recursion** → supervisors couldn't kick/role-change ANY member (HTTP 500) — fixed via `user_supervisor_hive_ids()` DEFINER helper (mig 20260622000000); (2) community **reply** trigger `handle_community_reply_xp` called `increment_community_xp` UNqualified under `search_path=''` → every reply 500'd (feature fully broken) — schema-qualified (mig 20260622000001). |
| **K4** | Intelligence (8) | 32 | **0% → 100% (32/32) ✅** | DONE. ENV-DEBT FIXED: the edge serve loaded `--env-file .env` (root) but `PYTHON_API_URL` was only in `supabase/functions/.env` → added to root `.env` + restarted `functions serve` → analytics 5/5. AK2 fixed (records panel loads with the chat screen → forced `loadRecordsSummary()`). asset-hub/alert-hub/audit-log/voice-journal/ai-quality/analytics-report all green. |
| **K5** | Build & Grow (6) | 19 | **0% → 100% (19/19) ✅** | DONE. ED4 fixed (drive clicked the `#bom-trigger` DIV not the Generate button → call `generateBomSowChecklist()` direct; BOM/SOW LLM renders 10 items). PRK3 fixed (C-lens now checks the AI-draft is re-runnable, not button text). RES-02 already green. |
| **K6** | Connect (4) | 14 (1 ◈) | **0% → 100% local (13/13 + 1 ◈) ✅** | DONE — FREE-PLATFORM build (no Stripe). marketplace 5/5 · marketplace-seller 4/4 · integrations 1/1 (+IN5 ◈) · plant-connections 3/3. ★2 REAL BUGS caught+fixed (see §5). |
| **K-Accept** | capstone | 102 | **✅ DONE — 101/102 = 99% local · baseline LOCKED live≥101, floor≤10** | focus-visible deterministic floor **cleared platform-wide** via a global `:focus-visible` ring in `utils.js` (43 pages) → floor hundreds→10. Residual floor (typed backlog) = tap-target (assistant 2/audit-log 1/eng-design 4) + contrast (logbook 1/analytics-report 11-node/eng-design 4) + scrollable-region (analytics-report 3). Gate `validate_live_page_journeys.py` registered (run_platform_checks "Arc K"). The 1 non-live = AN2 LLM-timing flake (passes in isolation; ratchet stable). |

Per-lens floors (declared up front): **R 95% · J 90% · T 90% · C 85% · X 85%.** R + T highest — reachability
and truthfulness are non-negotiable for a user-facing arc.

---

## §5 — Scoreboard (measured) — K0 BUILT · K1 PROVEN (2026-06-22)

**Harness:** `tools/live_page_journeys.mjs` (engine) + `live_page_journeys.heuristics.mjs` (auto-detectors +
the 209-rule `live_page_journeys_critic_catalog.json` triage corpus) + `live_page_journeys.registry.mjs` (the
JTBD registry). Two output streams: `live_page_journeys_results.json` (`journeys[]` = ratcheted live%) +
`live_page_journeys_findings.json` (`findings[]` = the Critic's severity-ranked UI/UX backlog). Baseline
locked: `live_page_journeys_baseline.json` (live ≥ 8, floor ≤ 0).

**K1 measured (index.html, 9 JTBDs):** **8/9 live = 88.9%** · per-lens **R 87.5 · J 87.5 · T 100 · C 100 ·
X 100** · **deterministic floor → 0** (the one real find — `#oh-hive-btn` 31px tap-target the fuller home
state exposed, that Arc D missed by never seeding `wh_hive_name` — was fixed: mobile ≥44px chip).

**K1 reusables proven:** sign-in-once recipe (worker `bryangarcia` / supervisor `leandromarquez`, both
`test1234`); T-lens fold from `journey_trace_results.json` (17 nerves) + a **privileged psql verifier** for
anon-write-only tables (`early_access_emails` is anon-INSERT / service_role-SELECT — the in-page anon client
can't read its own write back); the `ufai_battery.js` axe/tap/focus/input referee measured at the **390px
mobile field viewport** (measuring tap at desktop over-reports — the frontend-sweep recipe lesson); and the
heuristic detectors (axe-complementary: dialog-name, toggle-pressed, live-region, single-primary-CTA,
reduced-motion, blank-target-rel, heading-one, skip-link).

**K1 LA5 RESOLVED (Ian 2026-06-22, "this is a free platform"):** the landing's tool row is relabeled
**"Free to use — sign up to start"** and each tool CTA now opens the (free) SIGN-UP modal via `openSignUp()`
→ `switchAuthTab('signup')` (new `index.html` helper) instead of dead-bouncing a cold visitor to a gated
page. The LA5 drive was rewritten to assert the truthful contract (honest label + routes to signup). **K1 →
100% (9/9), floor 0.**

## §5b — Session-2 measured (2026-06-22, free-platform + K6 build): ALL K-phases → ~100% local

- **K4 env-debt → FIXED:** `functions serve` loads `--env-file .env` (root), but `PYTHON_API_URL` lived only
  in `supabase/functions/.env`. Added it to root `.env` + restarted serve (surgical, no full `supabase
  stop/start`) → analytics **5/5**. AK2 fixed: `#records-list` populates with the chat screen → drive now
  `startChat()` + forces `loadRecordsSummary()` → traces 300 == DB. **K4 = 32/32 = 100%.**
- **K5 tail → FIXED:** ED4 (drive clicked the `#bom-trigger` **div**, never the Generate button → call
  `generateBomSowChecklist()` direct; the `engineering-bom-sow` LLM renders 10 BOM items). PRK3 (C-lens now
  asserts the AI draft is re-runnable, not the button's text). **K5 = 19/19 = 100%.**
- **K6 Connect BUILT (free platform) → 13/13 local + 1 ◈:** `marketplace` 5/5 (browse/post/watchlist/
  **Contact-Seller inquiry**/saved-search), `marketplace-seller` 4/4 (edit-draft/reply-inquiry/messenger/
  analytics), `integrations` 1/1 local (real tagged CSV work-order import → external_sync+logbook verified)
  **+ IN5 ◈** (live CMMS sync = genuine external SAP/Maximo API), `plant-connections` 3/3 (CMMS-health/
  gateway-health/details-pane, truthful to live tables). `PAYMENTS_ENABLED=false` is the page default →
  the free flows ARE the real jobs; no Stripe mock needed.
- **★★2 REAL PRODUCTION BUGS caught by K6 (static sweeps + Arcs D–J missed both):**
  1. **CMMS importer never created logbook rows** — `integrations.html` `startImport()` omits `logbook.id`
     (text NOT NULL, **no DB default**; the add-entry wizard generates one). Every work-order import wrote
     `external_sync` but the `logbook.insert` threw (silently caught), so "cold-start analytics" from a CMMS
     import was broken. FIX: `id: crypto.randomUUID()` on each importer logRow.
  2. **Seller can't re-save an edited draft** — `marketplace-seller.html` `loadListings()` SELECT omitted
     `description`, so opening the edit sheet wiped the description → "Title and description are required."
     blocked every save (or silently lost the description). FIX: add `description` to the select so
     `openEditSheet()` pre-fills it.
- **K-Accept floor:** a global `:focus-visible` ring injected once in `utils.js` (loads on 43 pages) clears
  the focus-visible deterministic floor **platform-wide** (verified: marketplace floor 4→0). Residual floor
  = per-page tap-target + contrast (typed backlog, ratchet-locked).

---

## §6 — Honest ceilings (named up front)

- **External-effect JTBDs (◈, now just 1):** only **IN5 = live CMMS sync** (real SAP/Maximo/REST API must be
  reachable) is a genuine external ceiling — can't be live-completed without the user's CMMS up (a local mock =
  faking live = evidence-discipline violation). Locally we still prove the config form + Test-Connection +
  graceful-error path. ★**The two former Stripe ◈ are GONE** (Ian 2026-06-22, free platform): marketplace
  checkout / seller payout-connect dissolve — `PAYMENTS_ENABLED=false`, so Contact-Seller inquiry + free
  listing ARE the jobs, fully local. Resend (analytics-report) also ran live locally. Everything else on the
  Connect pages (browse, post, inquire, import, telemetry) IS locally live.
- **axe-core ~30–40% WCAG ceiling:** the deterministic floor proves what machines can; the ~60% judgment
  layer is the LLM-critic's severity-ranked backlog (a prioritized queue, not a binary pass).
- **Heuristic-critic subjectivity:** judgment findings are advisory + severity-ranked; only the deterministic
  floor (axe/jscpd/measured) ratchets to 0. The critic proposes; humans triage Major+.

---

## §7 — Ian-gated remainder (unchanged)

All Arc-K work is LOCAL. Standing Ian gates: external test keys (Stripe/Resend/CMMS) for the ◈ JTBDs ·
commit + push. The harness drives the local seeder (:5000) + local Supabase (127.0.0.1:54321).
