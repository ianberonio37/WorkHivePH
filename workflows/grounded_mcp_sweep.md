# Workflow: Grounded MCP Sweep (platform-wide, per page)

**Objective.** Drive any WorkHive page LIVE with the Playwright MCP as a *grounded*
observer — its pass/fail derived from the skills + the unified mega-gate layer
files, never invented — find what static checks can't, fix at root cause, then
crystallize every finding back into the gate AND the skills so the whole platform
gets less blind with each sweep.

**Born from.** The resume.html 50-batch sweep (2026-06-06) that found + fixed the
award-from-bullets recall gap. See resume-builder S23, [[project-resume-builder-2026-06-03]].

**Score every finding against the four pillars: Usability · Functionality ·
Adaptability · Internal Control (UFAI).**

---

## The loop in one line
Ground the observer (skills + gate files) -> map the live page -> drive UFAI
batteries with measured NUMBERS -> fix root cause + negative control -> trace the
blast radius to connected pages -> crystallize into the page's `validate_*` +
`journey-*` AND the cross-surface sentinels -> clean up + write lessons to every
skill the bug touched.

## Three non-negotiables (why this is not a naive probe)
1. **GROUNDED, not blind.** The MCP reuses the platform's own contracts. If it is
   about to assert something the gate already covers, it reuses it; only a genuinely
   NEW finding becomes a new L0 check or journey assertion. *Reuse the mega gate,
   never run a parallel probe.* (memory: [[reference-playwright-mcp-reuse-mega-gate]])
2. **MEASURED, not eyeballed.** Every battery returns numbers (rect sizes, font px,
   counts, recall ratios), so a finding is regression-testable.
3. **WEB-AWARE.** A page is a node; a fix ripples along shared edges (edge fns,
   `_shared/*`, tables/views, nav registry, canonical sources). "Done" = the blast
   radius is green, not just the one page.

---

## Phase 0 - Orient (cheap, every time)
- Live stack up: static server serving `http://127.0.0.1:5000/workhive/<page>.html`
  (Flask seeder rewrites cloud Supabase -> local `:54321`), Supabase `:54321`,
  edge functions (`supabase functions serve`), local URL rewrite confirmed in the
  served page source.
- **ENVIRONMENT-HEALTH PREFLIGHT (not just "up" -> "healthy"). Run BEFORE blaming any
  page. (Lesson 2026-06-06: a wedged Flask + 9-day-stale seed dates made 8/9 canonical
  parity tests RED with 400/500/`ERR_INSUFFICIENT_RESOURCES` and 16-34s loads — ZERO of
  it was a page bug; live, one-page-at-a-time, every tile matched canonical exactly.)**
  1. **Flask fast-200:** `curl -m5 -o/dev/null -w "%{http_code} %{time_total}s"
     http://127.0.0.1:5000/workhive/index.html` must return `200` in well under a second.
     A hang (HTTP 000 / multi-second) = the dev server has WEDGED (all threads blocked) —
     restart it (`Stop-Process` the :5000 PID, relaunch `test-data-seeder/venv/Scripts/
     python.exe app.py`) before driving anything. The Flask DEV server is not
     production-grade: heavy data volume (this DB: 17K logbook / 78K sensor rows) + a
     suite that rapid-fires heavy aggregation pages (hive/asset-hub/predictive) exhausts
     its sockets -> `ERR_INSUFFICIENT_RESOURCES`/500. Drive heavy pages ONE AT A TIME via
     MCP; restart Flask between heavy suite runs.
  2. **Seed freshness:** the newest event row must be ~today, else every time-windowed
     view (logbook team-feed 7d default, "closed today", "PM done today", sensor-24h,
     amc-today, the maturity gate) renders silently EMPTY and looks broken when it is not.
     Check: `docker exec supabase_db_workhive psql -U postgres -d postgres -c "select
     max(date) from logbook;"` — if > ~2 days old, refresh dates (next bullet) FIRST.
  3. **Non-destructive date refresh** (when seed is stale, and a full reseed is unwanted):
     shift each EVENT table forward by its OWN interval (newest->now()) so time-windows
     repopulate WITHOUT wiping the dataset — `test-data-seeder/refresh_seed_dates.sql`
     (logbook/pm_completions/sensor_readings/alerts/amc/shift_plans/inventory_transactions).
     DELIBERATELY EXCLUDE the derived-KPI tables (`pm_assets`, `asset_risk_scores`) so the
     verified pm-overdue / risk-alerts counts are preserved. Alert tables anchor on
     `detected_at` so `expires_at` lands in the future (= active). Verify nothing went
     future-dated after. A date-shift cannot DENSIFY sparse recent data (only a reseed
     can) — last-7-days may be thin (e.g. 1) even after; widen the filter to confirm the
     feature works.
  4. **On a SYSTEMIC red (many tests fail, slow times, 4xx/5xx/resource errors): suspect
     the ENVIRONMENT first, not the pages.** Reproduce ONE failing case live, one page at
     a time, and compare displayed-vs-canonical by hand. If it is perfect live, the suite
     red is env/load -> fix the env, re-run; do NOT crystallize a "page bug" that isn't one.
- Pollution-safe identity decided: in-memory only; NO cloud writes (Save / New /
  Switch / anything that inserts rows); do NOT hold a live MCP session while the
  journey suite runs (it competes with the suite's sign-ins -> flaky timeouts).

## Phase 1 - Ground the observer
Read, in this order, and derive the expectation set from them:
- **Skills:** the page's domain skill + the 5 always-in-scope (QA, Frontend,
  Performance, Mobile-Maestro, Security). Add Multitenant/AI-Engineer/etc. if the
  domain touches them.
- **Architectural truth:** `COMPREHENSIVE_STUDY_FULLSTACK_GATE.md`, `PLATFORM_ROADMAP.md`.
- **The page's L0 contract:** `tools/validate_<page>.py` IF one exists (resume,
  calc, voice-* have dedicated ones; most pages instead appear in the *cross-cutting*
  validators) + the page's rows in the 5 page lists (xss / schema / tenant_boundary /
  performance LIVE_PAGES + input_guards TARGET_PAGES) + `surface-coverage`.
- **The page's L2 contract:** `tests/journey-<page>.spec.ts`, `tests/surface-coverage.spec.ts`.
- **Canonical / data truth:** `canonical_registry.json`, `canonical_sources`, the
  `v_*_truth` views the page reads, `substrate_manifest`.
- **The gate map:** the 6 layers (L-1.5 miners -> Hardening -> Sentinel L2 -> L0
  ~330 validators -> L2 Playwright -> L4 meta) via `run_platform_checks.py`.

## Phase 2 - Find the test seam
- Probe `Object.keys(window)` for an exposed page module (resume exposes
  `window.WHResume.{get,set,openReview}`) + storage keys + buttons + file inputs.
- The seam lets you SEED and READ real state instantly -> ~30 deterministic
  scenarios per handful of `browser_evaluate` calls instead of clicking 60 inputs.
- **No seam = finding #1.** Add a tiny `window.WH<Page> = { get, set }` (IIFE
  internals are otherwise uncallable); it makes the page testable forever.

## Phase 3 - Drive the UFAI batteries (measured)
~50 scenarios grouped under the four pillars (see the per-page template). Most are
deterministic via the seam; reserve LIVE calls (uploads, real AI, edge fns) for the
few that truly need them; curl the live fn for the long tail of model-behavior
recall. Capture export blobs in-browser with a `URL.createObjectURL` shim to assert
OOXML/JSON without a download round-trip.

### F0 - Wired & Alive interaction audit (EXERCISE every clickable, do NOT just measure it)
**Non-negotiable, runs FIRST in the Functionality battery.** Measuring a button's
size/contrast/aria (Usability) is NOT proof it WORKS. A button can be 44px and
perfectly labelled yet be wired to an undefined handler, throw on click, or do
nothing. (Lesson 2026-06-06: the first three page sweeps measured geometry/a11y but
never exercised the clickables — the user caught it.)
1. **Enumerate** every visible clickable: `button, a, [onclick], [role="button"],
   summary, input[type=button], input[type=submit]` filtered by `checkVisibility()`.
2. **Static wiring check (covers ALL):** for each inline `onclick="fn(...)"`, extract
   the called names and assert `typeof window[fn] === 'function'` — an `onclick` that
   calls an undefined fn is a DEAD BUTTON (throws on click). Flag `href="#"` / `href=""`
   / `javascript:void` with no onclick as DEAD/❓ links (e.g. a logo that should be
   `index.html`).
3. **Live exercise + ASSERT THE OUTCOME (not just "it fired"):** click/fill every SAFE
   clickable in `try/catch`. "Didn't throw" is NOT proof it worked — a handler can fire
   cleanly and open the WRONG modal, go to the WRONG page, or "filter" with no change.
   After each interaction, assert the landed outcome on THREE axes — Act → **Assert**:
   - **WHERE it landed:** the resulting state is the CORRECT expected one — the *right*
     modal is now visible (by id/title/content), `location.href` is the *right* page
     (not a 404 / wrong target), a filter/sort/toggle actually changed the list IN THE
     RIGHT DIRECTION (e.g. status=Closed ⇒ every visible row is Closed), an input value
     was accepted + reflected (and empty/invalid ⇒ the guard toast, not a silent no-op).
   - **WHAT it shows (VALUE correctness — not just the right screen):** the values that
     landed must be CORRECT, judged against the platform's OWN contracts (never an
     invented expectation): (a) **canonical source** — read from the right `v_*_truth` /
     canonical source, not a raw table or a local re-derivation (`canonical_registry.json`,
     source chips, validate_canonical_anchor / truth-view-signal-trust); (b)
     **calculation** — any computed metric (count / MTBF / OEE / PM-compliance % / risk /
     low-stock) matches the canonical formula/standard (engineering-calc-validator,
     formula contracts, Standards-Alignment auditor, KPI count-query safety); (c)
     **cross-surface parity** — the same KPI here == on sibling pages == the DB
     (`journey-cross-surface-kpi-parity`, `canonical-lineage`); (d) **DB truth** — a
     written value equals the actual DB row (`flows/*_crud.py` DB-verified, write→read);
     (e) **honesty/provenance** — partial/stale values carry the honesty marker + a
     source chip. Flag DEFECT (calc bug / wrong view / drift / parity mismatch) vs
     CONTENT (the user's own data, e.g. a resume's "ISO 9001" — not a bug).
   - **WHEN it landed:** it SETTLED promptly — `waitFor` the expected effect with a
     timeout; assert no stuck spinner / perpetual "loading…", the async result actually
     arrived, and it didn't land-then-revert. A result that never arrives (dead fetch)
     is a finding even with no console error.
   - **CORRECT for WHO (role × experience):** re-run the same interaction per identity —
     the landing must be right FOR THAT user. supervisor ⇒ full destination; worker on a
     supervisor-only control ⇒ a helpful "ask your supervisor" (NOT the action, NOT a raw
     error); solo ⇒ the hive-gate, guided not stranded; a novice mis-click ⇒ recoverable.
     A denial that dead-ends, or a control that lands everyone in the same place
     regardless of permission, is a bug. The correct VALUE is also role-scoped (RLS):
     a worker sees only their hive's number, a supervisor the hive aggregate, solo the
     solo-scoped — cross-check against `journey-hive-isolation-property` (no cross-hive leak).
   Baseline checks still apply: (a) no thrown error, (b) no new console error. `el.click()`
   fires the real listeners, so a throwing/never-attached listener is also caught.
4. **Pollution-safe skip-list:** do NOT click writes/destructive — `save|submit|add|
   create|delete|remove|confirm|send|restock|adjust|reset|clear|export|sign-out`. For
   those, verify the handler is WIRED (static) and that submitting EMPTY hits the
   validation guard (the journey specs already cover the real write path). A click that
   opens a native file chooser = a working upload affordance (cancel it via
   `browser_file_upload` with no paths, which otherwise blocks the next MCP call).
5. **Report** dead/unwired/throwing clickables as conformance bugs (fix inline);
   `href="#"`-style IA nits as critique. Crystallize: the static "no `onclick` →
   undefined fn" check is a candidate L0 validator (deterministic, platform-wide).

### F-lineage - No PHANTOMS: every capture flows the canonical chain, every display traces to a source
Aside from clickables, EVERY data element must EARN ITS PLACE by completing the canonical
journey **Capture → Source/Fuel → Engine → Brain (v_*_truth) → Dashboard → Glue** — or it
is a useless phantom. Two element kinds, two lineage directions (reuse the platform's own
phantom gates as the oracle — don't invent):
- **CAPTURE** (`input`/`select`/`textarea`/`upload`/`toggle`/`radio`) needs a DOWNSTREAM
  CONSUMER: its value must write a canonical source table (via `canonical_capture_contracts`)
  that something later reads. Phantom if nothing consumes it or it writes a column no one
  reads. Oracle: **Phantom Capture Auditor** (reverse-lineage) + **Phantom Column Auditor**.
- **DISPLAY** (tile/number/label/badge) needs an UPSTREAM SOURCE: it must render from a
  `v_*_truth` canonical view with a source chip. Phantom if hardcoded / no JS setter / no
  source. Oracle: **Orphan KPI Tiles** + **Source-Chip Truth** + Calm-Dashboard wiring.
- **Field correctness at capture:** a `<select>`'s options must be the canonical enum (not
  drifted), inputs validate, required fields gate. Oracle: filter-case / role-string /
  category-values validators.
What the LIVE sweep adds over those STATIC auditors (which only prove a consumer EXISTS in
code): FILL the field with a known value → submit → TRACE it down the chain and assert at
each stage — (a) landed in the source table (DB-verified, `flows/*_crud.py`), (b) the engine
processed it to the right derived value, (c) it SURFACED on the dashboard/truth-view with the
CORRECT value (the WHAT axis above), (d) it PROPAGATED to connected pages (Glue /
cross-surface KPI parity), (e) scoped to the right role (RLS, no cross-hive leak). A value
that never reaches a consumer, or a tile that traces back to nothing, is a phantom → wire it
or remove it. **Honesty:** ephemeral/by-design fields (resume = in-memory draft, no source
table; client-side search; read-only display) are CONTENT, NOT phantoms — flag DEFECT
(should flow, doesn't) vs by-design, never dress one as the other.

### The IDENTITY MATRIX (single costume vs real distinct users) - REUSE the L2 role gate
"Diverse users" has TWO meanings - know which one the page needs:
- **Persona costumes (1 identity, sequential):** swap data/inputs through ONE
  signed-in identity (or in-memory). Enough for **Usability / Functionality /
  Adaptability** - the page logic does not care WHO you are. This is what the resume
  pilot used (private, owner-only, single-user page).
- **Real distinct identities - the platform's 3 ROLES (grounded):** REQUIRED for the
  **Internal Control + Multitenant** pillar. The roles are already defined - DO NOT
  invent your own:
  - `solo` (authenticated, NO hive context -> expects the hive-gate)
  - `worker` (active hive member, role=worker -> limited access)
  - `supervisor` (active hive member, role=supervisor -> full access)
  REUSE the existing harness, do not write a parallel one:
  `test-data-seeder/e2e_roles_runner.py` (34 pages x 3 roles, differential snapshots
  vs `e2e_permission_matrix.py:PERMISSION_MATRIX`), `e2e_roles_helpers.py`
  (`RoleContextFactory.get_page(role)`), and `tests/journey-hive-isolation-property.spec.ts`.
  The MCP sweep EXPLORES diverse role x data combinations live; a confirmed
  visibility/isolation bug is crystallized as a new row in `PERMISSION_MATRIX` (+ the
  isolation spec), not a throwaway.
  Assert: (a) role-gated UI matches `PERMISSION_MATRIX` per role, (b) `solo` hits the
  hive-gate, (c) a worker cannot READ another hive's rows (RLS) nor do supervisor-only
  actions, (d) owner-only edit/delete DENIES a non-owner, (e) no cross-hive leak.
  Decide in Phase 1: private single-user surface (costumes) or shared/tenant surface
  (run the role matrix)?

### The NOVICE axis - cross it with EVERY role (identity = role x experience)
Identity is 2-D: **role** (solo / worker / supervisor) x **experience** (novice /
experienced). The NOVICE ("dumb user", first-timer) is a MODIFIER applied to every
role, not a separate persona - and it bites ALL FOUR pillars, not just Usability
(this is the S22 resume novice audit, generalized). A novice = empty/first-run state,
no prior data, leaves fields blank, does steps out of order, fat-fingers destructive
buttons, doesn't know the jargon, often on a flaky connection / old phone. Run the
novice pass for each role and check all four pillars:
- **Usability:** first-run/empty state GUIDES to every start path (never assumes
  pre-existing platform data); plain labels, obvious "where do I start", no dead ends.
- **Functionality:** the core flow still works when fields are left blank or done out
  of order; empty/invalid input -> a friendly GUARD toast, never a crash or silent no-op.
- **Adaptability:** offline/flaky/old-device -> calm message + recovery, no stuck spinner;
  the first-timer can recover from their own mistakes.
- **Internal Control:** EVERY destructive action (remove / New / Switch / Delete) is
  UNDOABLE and/or auto-saves first (no silent data loss - the S22 undo-on-remove +
  worthSaving-counts-contact lessons); a permission DENIAL is EXPLAINED helpfully, not
  a dead-end or a raw error; a first-timer cannot accidentally trigger an
  irreversible / cross-tenant action without a confirm.
- **Role-crossed examples:** novice **solo** lands with NO hive -> must be guided, not
  stranded at the hive-gate; novice **worker** hitting a supervisor-only control -> a
  clear "ask your supervisor" message, not a silent fail/crash; novice **supervisor**
  (powerful, first-time) -> destructive/approve actions need confirm + undo so they
  don't nuke data on day one.

### REUSE the Layer-2 gate TYPES as the sweep's backbone (grounded, not a parallel probe)
The platform's L2 menu already encodes the test TYPES - the MCP sweep is the
EXPLORATORY layer on top, and every finding crystallizes back INTO these gates:
| L2 gate | Harness (test-data-seeder/) | Maps to sweep pillar/battery |
|---|---|---|
| **Smoke (~30s)** | `run_tests.py` Section 0 + `smoke.py` | load + presence + console-clean (Usability baseline) |
| **Role Permission (~3 min)** | `e2e_roles_runner.py` + `PERMISSION_MATRIX` | **Internal Control** - the Identity Matrix above |
| **Concurrent Edit (~2 min)** | `e2e_concurrent_runner.py` (async, 2 sessions; `last_write_wins`, `simultaneous_create`) | **Internal Control** - contention/realtime; assert conflict-warning OR clean last-write-wins, and no duplicate-key on simultaneous create |
| **CRUD (~2 min, DB-VERIFIED)** | `flows/*_crud.py` via `/api/run-crud-tests` | **Functionality** - UI write -> QUERY Supabase -> assert the write actually LANDED (not just DOM). Use for every data-source/tenant page; the resume pilot was in-memory and did NOT need it. |
| **UI Locks (Node ~6 min)** | the Node `tests/journey-*.spec.ts` suite | the L0->L2 crystallization target (lock the behavior) |
| **Visual Regression (~3 min)** | `visual.py` flow | **Usability** - screenshot vs baseline diff per page/template/breakpoint |
Page inventory is grounded in `e2e_roles_runner.py:TIER_PAGES` (34 pages / 5 tiers -
more complete than nav-hub's 28; reconcile the roadmap to it).

## Phase 4 - Fix at root cause + ALWAYS a negative control
- Root-cause (a deterministic miner, not a prompt tweak; a CSS rule, not a per-case
  patch).
- Pair every recall/inclusion fix with a **negative control** (input that MUST yield
  zero), AND test the **overlap case** (two layers both fire on the same item ->
  still one) - that is the dedupe sub-bug a negative control alone misses.
- Re-verify LIVE through the real UI, not just a unit path.

## Phase 4.5 - Blast radius (the web pass)
After any change, trace + re-verify the shared seams it touches:

| Shared seam | Who else it touches | Re-run |
|---|---|---|
| Edge function | every page that calls it | those pages' `journey-*.spec.ts` + edge-contract validators |
| `_shared/*` module | every fn importing it | the consumer guards |
| Table / view / RPC | every `v_*_truth` / `canonical_sources` reader | `tests/canonical-lineage.spec.ts`, `tests/journey-cross-surface-kpi-parity.spec.ts` |
| Nav registry / identity keys / `escHtml` | all pages | `codebase-integrity` skill (full cross-page audit) + `tests/journey-cross-page.spec.ts`, `tests/journey-megagate-cross-page.spec.ts` |
| Mobile / a11y baseline | all pages | `tests/journey-mobile-a11y.spec.ts` |
| Hive isolation / RLS | all tenant pages | `tests/journey-hive-isolation-property.spec.ts` |

## Phase 4.6 - Critique pass (the HARSH CRITIC) - opinionated, prescriptive, NEVER auto-applied
The batteries answer "does it meet the contract?" (referee). This pass answers "is the
design GOOD, and where should things actually live?" (critic). Be harsh: nothing earns a
pass for being merely "okay" - if a better state exists, name it. But HARSH != ungrounded:
every critique MUST cite what it is measured against, or it is just taste.
- **Grounding sources for a verdict (cite one):** a skill design rule; a UX law (Fitts -
  big/near targets for frequent actions; Hick - fewer choices; Jakob - match platform
  conventions; Miller - chunk; recognition-over-recall; progressive disclosure); an
  ATS/industry/standard; one of the four pillars; OR **a SIBLING PAGE that does the same
  thing better** (cross-page consistency is itself a contract).
- **Each critique is a structured "SHOULD-BE" record:**
  - **Now:** what it is today + the measured evidence (rect, step count, label text...).
  - **Should be:** the concrete prescription - "move Export into the sticky action bar",
    "collapse these 2 steps into 1", "this 429 toast should be a calm inline note".
  - **Where:** same page, OR **TRANSFER to page X** (information-architecture move:
    duplicated / mis-placed / orphaned control). This is the interconnection web applied
    to placement.
  - **Why:** the grounded heuristic/pillar/standard/sibling cited above.
  - **Pillar:** U / F / A / IC.   **Severity:** Blocker | Major | Minor | Polish.
    **Effort:** S | M | L.   **Priority** = severity vs effort (high-severity + low-effort first).
  - **Honesty flag:** DEFECT (a real problem) vs TASTE (my preference) vs CONTENT
    (the user's data, not the tool) - never dress taste as a defect.
- **Routing (Internal Control - the critic PROPOSES, you DISPOSE):** critique records are
  appended to `promotion_queue.md` (doctrine: "the engine discovers and drafts; YOU judge;
  nothing is auto-promoted"); disposition via `promotion_dispositions.json`
  (approved|rejected|snoozed). A CONFORMANCE bug is fixed inline (Phase 5); a CRITIQUE rec
  is NEVER auto-applied - an opinionated agent must not rewrite the product unilaterally.
- Run the critic per ROLE x EXPERIENCE (a novice supervisor critiques differently than an
  experienced worker), so the "should-be" reflects who actually struggles.

## Phase 4.7 - The HOLISTIC / CROSS-PAGE critic (the editor with a map, not the referee with a ruler)
**Why this phase exists (2026-06-07, user insight):** Phases 0-4.6 are PER-ELEMENT and
CONTRACT-GROUNDED — they walk one clickable/input/tile and ask "does THIS meet a contract?".
That makes them structurally BLIND to the highest-value UFAI judgments, because:
  1. redundancy / overlap are RELATIONSHIPS between elements & pages — you cannot find a
     duplicate by examining one item in isolation;
  2. "grounded = cite a measurable contract" biases the critic to the measurable — "this is
     redundant / shouldn't exist / the IA is wrong" has NO numeric oracle, so it's never raised;
  3. there's no JOB/intent model, so it can't see that 3 pages answer the same question 3 ways;
  4. scope is one page/session, but redundancy is inherently cross-page;
  5. it asks "does it conform / is it placed well?", never "SHOULD THIS EXIST?".
A purely element-driven sweep finds tap sizes and enum typos and misses that pm-scheduler +
dayplanner + shift-brain all re-derive "overdue/due PM" (and that the duplication is what let
the dayplanner `'closed'`-vs-`'done'` WHAT-bug survive — **redundancy CAUSES the value bugs**).

**So this pass is MODEL-DRIVEN, not contract-driven, and CROSS-PAGE, not per-page:**
- **Build / extend a FUNCTION INVENTORY first** (`.tmp/sweep/function_inventory.md`): every
  action, KPI, and capture x which pages expose it x which source/RPC/view it uses. You can
  only spot a duplicate against an inventory, never element-by-element. Grow it each sweep.
- **Cluster by JOB-TO-BE-DONE** ("plan my day", "know what's overdue", "hand over my shift",
  "capture a thought") and flag: (a) one job served by >1 page (redundant surface); (b) a
  control reachable >=3 ways (overlap); (c) a KPI/logic computed in >1 place (drift risk).
- **The canonical rule that kills the class:** a KPI/logic computed on >1 surface is a
  redundancy DEFECT -> collapse to ONE shared source (`v_*_truth` / shared helper / RPC) so it
  cannot drift. (This is the cross-surface-parity contract turned into an IA mandate.)
- **Ground each holistic verdict in JUDGMENT sources** (since there's no numeric contract):
  a UX law (Hick - fewer choices; Tesler - irreducible complexity lives in ONE place; Jakob -
  match conventions; recognition-over-recall; progressive disclosure), OR a sibling page that
  does it better, OR one of the four UFAI pillars. Flag honestly TASTE vs DEFECT vs CONTENT.
- **Route + dispose like 4.6** (`sweep_critiques.json` -> promotion_queue.md, NEVER auto-applied)
  but tag the rec `scope: cross-page` so the holistic class is visibly distinct from element nits.
- **Outputs are recs, not edits.** Collapsing 3 redundant surfaces into 1 is a product decision
  the human makes; the critic NAMES the redundancy + the merge target + the cost of leaving it.
- **TOOLING to give this pass teeth (researched 2026-06-07, reputable sources):**
  - **`jscpd` / `cpd`** (github.com/kucherenko/jscpd) — deterministic copy-paste/clone detector;
    tokenizes embedded `<script>`/`<style>` in HTML, Rabin-Karp, `ai` token-efficient + `sarif`
    reporters, and its OWN MCP server. The deterministic half of redundancy: catches TEXTUAL
    clones (the 18x "verdict+simple-card" block) as data. Wire as a G0 validator
    `validate_clone_debt.py` with a forward-only baseline ratchet (like modal-a11y/selector):
    `cpd --pattern "*.html,*.js" --min-tokens 50 --reporter json`. Does NOT find SEMANTIC
    redundancy (two different "overdue" implementations) — that's this phase's model-driven job.
  - **Nielsen 10 / Norman 7 / WCAG POUR** (canon; structure borrowable from
    github.com/mastepanoski/claude-skills, severity 0-4) — the citable RUBRIC for the judgment
    verdicts (replaces ad-hoc taste; maps 0-4 -> Blocker/Major/Minor/Polish).
  - **`@axe-core/playwright`** (Deque) — industry WCAG engine in the journey specs; ratchet
    violations (replaces hand-rolled a11y approximations).
  - **UXAgent** (github.com/neuhai/UXAgent, Amazon Science) + arXiv 2512.04262 — LLM-persona
    goal-driven usability simulation = the novice x role pass as a journey sim (phase-2).
  - **Playwright `accessibility.snapshot()` cross-page diff** — cheap duplicate-affordance (overlap) signal.
  See `.tmp/sweep/function_inventory.md` (the standing cross-page map) + [[reference-holistic-critic-tooling]].

## Phase 5 - Crystallize + prove green
- Add forward-only checks to `tools/validate_<page>.py` (create one if the finding
  warrants a dedicated guard) and assertions to `tests/journey-<page>.spec.ts`.
- If a shared seam changed, crystallize the cross-page contract into the relevant
  cross-surface sentinel, not just the one page.
- Run guards. **Flake vs regression:** a regression fails DETERMINISTICALLY; a flake
  DECAYS on `--last-failed` re-runs (e.g. 7->5->2->0) and every trace points at the
  sign-in FIXTURE before any feature code. Run Playwright with
  `node node_modules/@playwright/test/cli.js test <spec> --reporter=list` (npx
  breaks in this repo). For the full gate: `python run_platform_checks.py --fast`.

## Phase 6 - Clean up + cross-skill writeback
- Delete any rows the session created (by `auth_uid` / marker); confirm the journey
  suite starts clean.
- Per the Skill Self-Improvement Loop in CLAUDE.md: write the lesson to EVERY skill
  it touched (one bug usually teaches 3-4), each from its own angle, then project
  memory + `MEMORY.md` index + the page's roadmap row.

## Definition of Done (per page)
- [ ] UFAI batteries run, each returning numbers (role x experience, incl. the NOVICE pass).
- [ ] Every real CONFORMANCE bug fixed at root cause + negative control + overlap case.
- [ ] Critique pass done; top "should-be" recs (incl. any "transfer to page X") appended to
      `promotion_queue.md` - NOT auto-applied.
- [ ] Blast radius traced; connected pages + cross-surface sentinels green.
- [ ] `validate_<page>.py` (or the cross-cutting validators) + `journey-<page>.spec.ts` green.
- [ ] DB clean (zero pollution); MCP browser closed.
- [ ] Lessons written to all relevant skills + memory + index + roadmap row.

## Pitfalls (learned the hard way)
- Holding a live MCP session OR editing an edge fn (triggers a re-bundle) WHILE the
  journey suite runs causes sign-in-fixture flakes. Quiet the stack, then re-run.
- A presence-only `validate_*` check ("function exists") does NOT measure recall -
  pair it with a LIVE labeled-corpus run on a NEW corpus each sweep (an LLM "reliably
  does X" claim is a sample, not a guarantee).
- The dpr trap: `browser_resize(390)` can yield CSS width 487 at dpr 0.8 - set
  physical `390 * dpr` to read TRUE 390 CSS px.

See also: `workflows/grounded_mcp_sweep_page_template.md` (the per-page fill-in).
