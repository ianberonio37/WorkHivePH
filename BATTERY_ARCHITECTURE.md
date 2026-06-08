# BATTERY_ARCHITECTURE.md — the UFAI Battery Family

> **Status:** doctrine + **BUILT** (2026-06-08). The model was agreed first; the
> full INTERFACE column (① Component · ② Page · ③ Journey · ④ Platform) is now
> implemented and verified (see §6). Sibling of `AI_SURFACE_MAP.md` and
> `AGENTIC_RAG_ROADMAP.md`. All LOCAL/uncommitted.
>
> **One-line:** the "UFAI battery" is not one tool — it is **one engine applied at
> four ALTITUDES** (component · page · journey · platform), across **three
> SUBJECTS** (interface · AI-behaviour · data), under **one doctrine** (referee
> fixes inline, critic surfaces for a human to dispose — never auto-collapse).

---

## 1. Why this doc exists

We kept saying "the battery" for several different things: the single-page
`ufai_battery.js`, the `analytics_correctness.js` per-tile parity, the
`companion_battery.js` AI-behaviour battery, the IA-streamlining surveyor. They
are not rivals or duplicates — they are the **same idea at different zoom
levels**. This doc names the levels so every future battery has an obvious home
and we never rebuild the kernel.

The model is deliberately the **frontend testing pyramid** (component → page →
journey → e2e) crossed with **Brad Frost's atomic design** (atoms → molecules →
organisms → pages). We are applying those altitudes to *quality auditing*, not
just to unit tests.

---

## 2. The two axes + the lenses

### Axis A — ALTITUDE (the zoom: how much of the product is in frame)

| # | Altitude | The question | Atomic-design analog | Testing-pyramid analog |
|---|---|---|---|---|
| ① | **Component** | Is this PART right + consistent **everywhere it appears**? | atom / molecule | component test |
| ② | **Page** | Is this SCREEN usable + correct? | organism / page | page / integration |
| ③ | **Journey** | Can a user **complete the job** across pages? | flow across templates | user-journey / e2e |
| ④ | **Platform** | Is the whole PRODUCT coherent? | the design system itself | site-wide audit |

### Axis B — SUBJECT (what kind of thing is under test)

| Subject | What it judges | Today's battery |
|---|---|---|
| **Interface** | pixels, a11y, wiring, display-correctness | `ufai_battery.js` (UFAI: U/F/A/I/C) |
| **AI behaviour** | Agent · Memory · RAG · Safety | `companion_battery.js` (`__CSB`) |
| **Data / source-of-truth** | rendered value == the exact canonical field | `analytics_correctness.js` |

### Cross-cutting LENSES (apply in EVERY cell of the grid)

- **The 5 pillars** — Usability · Functionality · Adaptability · Internal-control · Correctness.
- **Role × experience** — field / supervisor / engineer × novice / experienced.
- **Referee vs Critic** — referee = measured DEFECT, fixed inline; critic = opinionated TASTE/CONTENT, surfaced for disposal.
- **Static vs Live** — a deterministic static/parse pass (cheap, env-free) + a live MCP/Playwright pass (rendered values, real interaction).

---

## 3. The grid — altitude × subject, mapped to what EXISTS

> ✅ mature · 🟡 partial / exists-but-not-unified · ⬜ gap

| | Interface (UFAI) | AI behaviour | Data / truth |
|---|---|---|---|
| **① Component** | ✅ `__UFAI.component()` (live) + `tools/survey_component_consistency.py` (static) | n/a | 🟡 per-tile parity is value-level (`analytics_correctness.js`) |
| **② Page** | ✅ `ufai_battery.js` v1.4.0 — **the kernel** | 🟡 `__CSB` is page-scoped today | ✅ `analytics_correctness.js` |
| **③ Journey** | ✅ `journey_battery.js` (`__JOURNEY`) + `tools/plan_journey_battery.py` + L2 specs | ✅ `tests/journey-companion-comprehensive.spec.ts` | 🟡 cross-surface KPI parity spec |
| **④ Platform** | ✅ `tools/run_battery_family.py` unifies IA surveyor (P1–3) + Component + Persona + `codebase-integrity` | 🟡 `validate_companion_stack.py` G0 | 🟡 canonical-drift miner / `validate_user_facing_kpi_canonical.py` |

**Reading of the grid (updated 2026-06-08 — family BUILT):** all four INTERFACE
altitudes now have a battery. Page ② is the mature kernel; Component ① (the former
gap) shipped both layers; Journey ③ has a reusable `__JOURNEY` driver + a grounded
plan; Platform ④ unifies the headless runners into one report + verdict. The
remaining 🟡 cells are on the *behaviour* and *data* subjects (lift `__CSB` to more
altitudes; wire KPI-parity into the platform run) — incremental, not new scopes.

---

## 4. The architecture: ONE kernel, N drivers (extend, don't rebuild)

The single-**page** battery IS the kernel. Every other altitude is a thin
**driver** that *composes* the kernel — it does not re-implement pillars,
boot, the defect/critic schema, or the disposition pipeline.

```
                         ┌─────────────────────────────────────────┐
                         │  KERNEL  (ufai_battery.js, the PAGE run) │
                         │  boot(axe/web-vitals/CWV) · pillars      │
                         │  U/F/A/I/C · defect+critic schema ·      │
                         │  inventory() · enumerateStates()         │
                         └───────────────┬─────────────────────────┘
        ┌───────────────────────┬────────┴───────────┬────────────────────────┐
   ① COMPONENT             ② PAGE (=kernel)       ③ JOURNEY               ④ PLATFORM
   run pillars on each     the kernel itself      run kernel at each      aggregate page runs
   instance of a           (already mature)       step of a JTBD +        + cross-page invariants
   selector, DIFF across                          assert state carries    (IA redundancy, nav
   instances                                      + KPI agrees per step    integrity, KPI parity)
```

- **① Component driver** — given a selector (e.g. `.simple-card`, the
  `:detail_panel`, a stepper), find every instance across pages (the IA corpus
  already lists them), run the kernel's pillars on each, and **diff**: same a11y
  name? same tap size? same behaviour? An inconsistency *between instances* is the
  component defect this scope exists to catch. Analog: Storybook test-runner + axe.
- **② Page** — the kernel, unchanged.
- **③ Journey driver** — walk a job-to-be-done (`__UFAI.inventory()` + the
  Phase-3 persona model give the path), run the kernel at each step, and assert
  the two journey-only invariants the page battery can't see: **state continuity**
  (selection/identity carries) and **number continuity** (the same KPI shows the
  same value at every step — this makes the Phase-3 "overdue drift" finding
  executable). Analog: Playwright user-journey test.
- **④ Platform driver** — run the page battery across all pages and add the
  cross-page invariants: IA redundancy (`survey_ia_redundancy.py`), nav/identity/
  shell integrity (`codebase-integrity`), and source-of-truth parity. One run,
  one verdict. Analog: unlighthouse / pa11y-ci / Lighthouse CI / Axe Monitor.

**The shared spine (every altitude uses it, none re-invents it):**
`referee` (fix inline) · `critic` → `ia_*_candidates.json` / battery `critic.candidates`
→ `ufai_ingest.py` → `sweep_critiques.json` → `flywheel_orchestrator` →
`promotion_queue.md` → **you dispose** via `promotion_dispositions.json`.

---

## 5. Doctrine (binds at every altitude)

1. **Referee fixes DEFECTs inline; critic SURFACES taste/IA for a human.** Never
   auto-collapse UI, never auto-merge pages, never auto-delete a tile. The engine
   proposes; you dispose.
2. **Same-NAMED ≠ same-DERIVATION.** A field/label/unit that looks identical may
   be a different computation (OEE-availability 96.1% ≠ reliability-availability
   99.2%; asset "Pending approval" ≠ parts "Pending approval"). Every scope
   carries a VERIFY-FIRST step before calling a match a bug or a redundancy.
3. **Coverage honesty.** A single run is never a full sweep — each battery states
   what it did NOT see (other states, other roles, the live half).
4. **Static is the cheap spine; live is the proof.** Build the deterministic pass
   first (env-free, reproducible); escalate to the live MCP pass for rendered
   values + real interaction.
5. **Automated catches ~30–40% of WCAG** (reading order, keyboard traps,
   contextual clarity need a human) — so the critic/human-dispose half is not
   optional polish; it is half the system.

---

## 6. Build order — ✅ ALL BUILT (2026-06-08)

1. ✅ **① Component battery** — `tools/survey_component_consistency.py` (static
   spine: census + shape-consistency + capability-registry cross-ref) +
   `__UFAI.component()` (live DOM-accurate shape audit). First run: 52 `.simple-card`
   + 8 `.sum-card`, **one consistent shape each → 0 drift** (the design system is
   consistent — a clean, valid result).
2. ✅ **④ Platform battery** — `tools/run_battery_family.py` runs the headless
   family in dependency order → `battery_family_report.md` (one grid + one verdict).
   Distinct from `run_platform_checks.py` (the L0 validator gate).
3. ✅ **③ Journey battery** — `journey_battery.js` (`window.__JOURNEY`: sessionStorage
   step journal + state/number continuity verdict) + `tools/plan_journey_battery.py`
   (3 tile-validated journeys anchored to Phase-3 confusions + their `sweep:ia:*`
   candidates). Execution is the live MCP step.

**Next (incremental, the 🟡 cells):** lift `__CSB` (behaviour) to journey/platform
altitudes; wire KPI-parity (data) into `run_battery_family.py`; optionally gate the
family verdict in CI.

---

## 7. What already exists (so we extend, not rebuild)

| File / asset | Altitude · Subject | Role |
|---|---|---|
| `ufai_battery.js` (v1.4.0) | ②/① Page+Component · Interface | **the kernel** (U/F/A/I/C + `inventory()` + `component()`) |
| `tools/survey_component_consistency.py` | ① Component · Interface | static shape-consistency + capability cross-ref |
| `analytics_correctness.js` | ② Page · Data | per-tile oracle parity |
| `companion_battery.js` / `__CSB` | ② Page · AI-behaviour | Agent·Memory·RAG·Safety |
| `tools/survey_ia_redundancy.py` | ④ Platform · Interface | cross-page redundancy map (IA P1) |
| `tools/score_ia_streamlining.py` | ④ Platform · Interface | redundancy rubric (IA P2) |
| `tools/ux_persona_walkthrough.py` | ③→④ Journey/Platform | persona confusion walkthrough (IA P3) |
| `journey_battery.js` / `__JOURNEY` | ③ Journey · Interface | live state + number continuity driver |
| `tools/plan_journey_battery.py` | ③ Journey · Interface | grounded journey plan generator |
| `tools/run_battery_family.py` | ④ Platform · all | **the family orchestrator** (one run + verdict) |
| `codebase-integrity` (skill) | ④ Platform · Interface | nav/utils/identity/hive/escHtml audit |
| `validate_companion_stack.py` | ④ Platform · AI-behaviour | G0 gate on companion stack |
| `ufai_ingest.py` → `sweep_critiques.json` | all | the shared critic→dispose pipeline |
| `tests/journey-*.spec.ts` | ③ Journey | live L2 flow specs |

---

## 7b. Relationship to the Unified Mega Gate — the battery is **G3**

The battery is NOT a parallel quality world; it is a registered layer of the
6→7-gate model in `UNIFIED_MEGA_GATE.md` — **G3 (UFAI Battery / UX-quality audit)**.
It overlaps G2 (Comprehensive E2E) at the live-page boundary but does a different
job, and it must never replace G2:

| | **G2 — Comprehensive E2E** | **G3 — UFAI Battery** |
|---|---|---|
| Asserts | the FLOW works (CRUD saved, role denied, journey completes) | it's usable/accessible/fast/consistent/coherent (axe·CWV·focus·IA·component) |
| Enforcement | **hard gate** — deterministic pass/fail, committed specs | referee fixes inline + **critic surfaces → human disposes** |
| Scope | one altitude (page-flow) | four altitudes (component→platform) |

**Why it can't BE G2:** G2's value is being a committed deterministic gate; the
battery's critic half is deliberately non-gating. Swapping them loses the hard
functional gate. By its own header doctrine `ufai_battery.js` *reuses* the L2/G2
suite and ADDS ONLY the 5 things it lacks (axe/CWV/focus/prod-path/dpr).

**How it connects (the bridges, same as every other gate layer):**
1. **Harden DOWN (GH):** a stable G3 **DEFECT** → a G0 validator (cheap, gating,
   forever). Precedent: the battery's prod-path check became `validate_prod_path_leak.py`.
2. **Graduate (toward G2):** a G3 **journey-continuity** assertion → a committed G2
   spec so it gates behaviourally.
3. **Surface → dispose:** G3 **critic** candidates → `sweep_critiques.json` →
   `flywheel_orchestrator` → `promotion_queue.md` → `promotion_dispositions.json`.
4. **Ratchet (Rule B):** `tools/run_battery_family.py --gate` compares to
   `battery_family_baseline.json` (only moves down; auto-tightens on reduction;
   `--update-baseline` to accept intentionally). This is the pre-commit G3 step,
   slotted into the Mega Gate sequence after G2. Proven: regression → exit 1,
   at-baseline → exit 0.

**Rule compliance:** Rule A (every production change lands with a gate change) —
an accepted G3 fix lands with its G0 validator via GH. Rule B (baselines only move
down) — the `--gate` ratchet. Rule C (every fix updates ≥3 skills) — G3 findings
carry skill writebacks like any other. In the 13×6 coverage matrix
(`COMPREHENSIVE_STUDY_FULLSTACK_GATE.md`), G3 fills the UX / a11y / cross-page-
coherence cells that static validators structurally can't cover.

## 8. References

- **Internal:** `qa-tester` skill ("the critic is blind to cross-page redundancy
  → build the editor-with-a-map", now fulfilled by the IA surveyor),
  `codebase-integrity` skill, `AI_SURFACE_MAP.md`,
  `project-ia-streamlining-phase1-2026-06-08` (memory).
- **External:** [Frontend Testing Pyramid (Meticulous)](https://www.meticulous.ai/blog/testing-pyramid-for-frontend) ·
  [Modern Frontend Testing Strategy (Feature-Sliced Design)](https://feature-sliced.design/blog/frontend-testing-strategy) ·
  [Atomic Design — Brad Frost](https://atomicdesign.bradfrost.com/chapter-2/) ·
  [User Journey Testing (BugBug)](https://bugbug.io/blog/software-testing/what-is-user-journey-testing/) ·
  [End-to-End User Journeys (TestResults)](https://www.testresults.io/definitions/end-to-end-user-journeys) ·
  [axe / Pa11y / Lighthouse CI in DevOps (Accesify)](https://www.accesify.io/blog/accessibility-testing-automation-axe-pa11y-lighthouse-ci/) ·
  [Accessibility Evaluation Tools — W3C/WAI](https://www.w3.org/WAI/test-evaluate/tools/list/).
