# ANALYTICS ENGINE — Full UFAI Rubric drive → `analytics.html` (Execute arc, drafted for a fresh window)

**Drafted 2026-07-15**, on Ian's (e): *"wrap this up, we will implement this UFAI UI UX Rubric roadmap to
other page, this time will be for Analytics Engine."* Same proven method that took **hive.html** and the
**home dashboard (`index.html #ops-home`)** to compliance-100%.

> **TARGET: `analytics.html`** (2639 lines / 157KB — the Analytics dashboard).
> Secondary: `analytics-report.html` (89KB, the print/PDF variant — grade it too; print has its own rules).

## GROUND (retrieve-first — do NOT re-derive; it is all banked)
1. **The ruler:** `substrate/reference/ufai-ux-rubric.md` (17 classes A–R, ~46 dims, every rule cited).
2. **The method + honest scoring:** `feedback_ufai_per_dim_measurement_drive` (measure per-dim LIVE; report
   **compliance + quality-curve**, NEVER a flat false-100 — hive landed ~97, home ~94).
3. **The two most load-bearing build memories:**
   `feedback_home_dashboard_ufai_and_i18n_build` (the i18n recipe + whole-page chrome-leak + gate-sweep)
   and `feedback_layout_harmony_and_view_switch_cls` (class R + the view-switch CLS root-cause).
4. **Skills (Skill-First):** **dataviz (MANDATORY — read BEFORE touching any chart)**, frontend, designer,
   qa-tester, mobile-maestro, performance, analytics-engineer.

## WHY THIS PAGE IS DIFFERENT (grounded, already probed)
- **61 chart/gauge/plotly references → class E1 is THE dominant class here.** E1 is explicit: an operational
  dashboard uses **length + 2D position (bars)** for quantities and **NEVER gauges/pie (area/angle)**; color
  for **categories only**; make the ONE key metric distinct (Von Restorff). **Expect real E1 violations** —
  audit every chart type. Pair with the `dataviz` skill (palette/mark specs) + `analytics-engineer`.
- **A `data-tab` view-switcher (~line 144-147) → the CLS trap.** Panels hidden until JS reveals them insert
  late → the footer jumps. FIX = reserve the view SHELL (`min-height:100vh` on the tab-panel container),
  NOT the inner cards. (hive.html 0.233→0.002 exactly this way.)
- **Zero i18n** (0 `WH_LANG`/`_t`/`data-i`) → N1 needs the FULL recipe (below).
- **157KB already** → render-budget is tight; index.html tipped over. Prefer CSS/text edits over new blocks.

## THE PROVEN FLOW
1. **Walk EVERY tab/state live** (Playwright MCP, 430x932 + desktop). Sign in `pabloaguilar`/`test1234`
   (hive `c9def338-fd73-4b19-8ef1-ee57625953d6`). Expand every disclosure; reach the TRUE bottom.
2. **MEASURE per-dim** (`browser_evaluate`): axe-core CDN inject → C2/F2 (target 0/0); `getBoundingClientRect`
   min-dim over interactives → **F1 (≥44px WIDTH *and* height)**; `font-variant-numeric` on KPIs → C4;
   `PerformanceObserver{layout-shift,buffered}` → **I1 CLS** (identify the shifting NODE via `e.sources`);
   distinct inter-block gaps → **R1** (all multiples of 8?); `body.scrollWidth > innerWidth` → **R2 overflow**;
   **chart-type inventory → E1**. Build `ANALYTICS_UFAI_ROADMAP.md` (measured per-dim table + disposition map).
3. **DRIVE each violation → 100% compliance.**
4. **VERIFY the WHOLE artifact** — **FULL-PAGE screenshot** (`fullPage:true`), axe 0/0 in EN *and* FIL,
   0 console errors, gates green.
5. **SCORE honestly:** compliance (cited-rule violations → none = 100%) + quality-curve (subjective ~ceiling).

## GOTCHAS — every one paid for in blood on hive/home (do NOT re-learn)
- **★Whole-page disposition:** chrome living OUTSIDE the hidden wrapper LEAKS into the other state. On
  index.html the marketing `<footer>` + "Get Early Access" CTA leaked into the signed-in dashboard.
  **And the hide MUST live in the SHARED render fn that EVERY path calls — not one entry point.** Putting it
  only in `_showOpsHome` re-leaked via the direct `_initDashboard` paths. Build the CURRENT→TARGET
  KEEP/MOVE/MERGE/DELETE map BEFORE implementing.
- **★A viewport screenshot LIES.** The footer leak survived a viewport-only pass and was only caught by a
  FULL-PAGE screenshot. Always `fullPage:true`.
- **★Skeletons can REGRESS CLS.** A loading skeleton whose height doesn't EXACTLY match the (variable) real
  content shifts twice and made CLS 0.0055→0.118. **Reserved `min-height` on the async block beat it.**
  Measure before keeping any "improvement" — verify-or-revert.
- **F1 fails on the MIN dimension** — a 44px-tall but 35px-wide toggle FAILS. Add `min-width:44px`.
- **i18n recipe (N1):** `WH_LANG` (persist `wh_lang`) + `_t(en,fil)` for JS-rendered + `_tv()` phrase-map for
  a render-fn's fixed label/cta set + `setLang()`. Static → `data-i` + a FIL dict; **wrap a label's TEXT in
  its own `<span data-i>`** (data-i on an `<a>` holding an SVG nukes the icon). **Add a sync-on-load** or a
  returning FIL user sees mixed EN/FIL. Shared `utils.js` renderers: use a **safe `_t` fallback**
  (`window._t || (en=>en)`) so non-i18n pages never break. DATA (names/counts/IDs) stays English.
- **★Gate-sweep after i18n** (all three bit me): toggle via `addEventListener` NOT inline `onclick`
  (`validate_csp.py` ratchet) · every new empty `catch(_){}` needs `/* empty-catch-allow: … */`
  (`validate_empty_catch.py`) + **sweep siblings** · a per-state h1 → "multiple h1"
  (`validate_heading_hierarchy.py`) → SHORT `<!-- heading-allow: … -->` **within 300 chars** of the tag.
  Re-run `python tools/build_substrate.py` after edits (PKS freshness).
- **Section labels should be real `<h2>`** (not `<p>`) for screen-reader navigation — `.oh-sec-lbl`-style
  classes already zero the heading margins, so it is visually identical.
- **Isolate MY regression from PRE-EXISTING debt.** The tree carries 800+ uncommitted prior-session files, so
  the aggregate gate shows reds that are NOT yours (Design Tokens raw-hex, Partial-Label, Canonical Anchor,
  Deep-Link, Memory M3.1). Run the SPECIFIC validator; only own what your diff caused.
- **Don't change GOOD design to hit a rubric number.** C1's "≤2 primary + 2 secondary" is in real tension with
  E1's "color for categories" on a dashboard — semantic KPI colors are CORRECT; flattening them regresses
  glanceability. Classify by evidence; a design-taste change is Ian's proposal-first call.
- Playwright: MCP profile can hold a stale lock → kill the leftover chrome tree for
  `--user-data-dir=*mcp-chrome-*` (never the user's own Chrome). `npx` breaks on the `&` path — use
  `node node_modules/@playwright/test/cli.js`.

## Gate + commit
Local only. `validate_no_em_dash.py` · `validate_heading_hierarchy.py` · `validate_empty_catch.py` ·
`tools/validate_csp.py` · `tools/build_substrate.py` must stay at baseline. Commit/deploy Ian-gated.

NEXT: fresh window → Ground (rubric + the 2 build memories + **dataviz skill**) → walk every tab live →
measure per-dim (E1 chart inventory first) → `ANALYTICS_UFAI_ROADMAP.md` → drive → full-page verify → score honestly.
