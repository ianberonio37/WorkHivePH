# HIVE BOARD — v4 UFAI Redesign → real `hive.html` (Execute arc, drafted for a fresh window)

**Drafted 2026-07-14** (Night-Crawler session `9817bfd9`, wrapping on Ian's explicit (e): *"I love it. wrap
this all up, implement v4 into the real hive.html for real, in fresh context window."*). This is the
**Execute** phase of the Hive-Board UFAI redesign — Ground/Ideate/Roadmap are DONE (the harvest + rubric +
v1→v4 mockups). The fresh window ports the approved **v4** proposal into the real page, wired to live data.

> **What this arc IS.** Take the approved v4 Hive-Board redesign (proposal-first, Ian-loved through 4
> iterations) and implement it in `hive.html` **for real** — live data, mobile-first, accessible,
> gate-locked — WITHOUT regressing the page. Grounded end-to-end in the cited **UFAI-UX rubric** (14
> classes / 30 dims, 51 distilled reputable sources). Complements the existing `HIVE_BOARD_DEEP_ARC.md`
> (the broader Hive PDDA) — this doc is specifically the v4-visual/UX execution.

---

## Ground (read FIRST — everything is already banked, retrieve don't re-derive)

- **The ruler:** `substrate/reference/ufai-ux-rubric.md` — the 14-class/30-dim cited rubric. Also
  `memento_retrieve.py "ufai ux rubric"`. Full source rules: the 51 `substrate/external/external-ux-*.md`
  chunks (retrieve the named one). Do NOT re-crawl — it's comprehensive.
- **The approved design (the SPEC):** two durable mockups on Ian's Desktop —
  `C:/Users/ILBeronio/Desktop/HiveBoard_UFAI_BeforeAfter/_MOCKUP_v4_board.html` (the board) and
  `_MOCKUP_v4_firstrun.html` (the first-run empty state). Read them — they are the pixel/'structure spec.
  Screenshots `0_BEFORE_vs_AFTER_v4_desktop.png`, `14_v4_ENGLISH_vs_TAGALOG.png`,
  `12_AFTER_v4_FIRSTRUN_onboarding.png`, `13_AFTER_v4_mobile.png` in the same folder.
- **The target:** `hive.html` (~271KB, **inline** `<script>` — like resume.html, NOT externalized). Its
  `learn/` subdir. Skill-first reads BEFORE editing: **frontend, designer, mobile-maestro, qa-tester,
  multitenant-engineer** (hive gate), **performance** (render-budget), **security** (escHtml/CSP).
- **Prior arc:** `HIVE_BOARD_DEEP_ARC.md` (the axes + the "4-5 second" dissatisfaction that started this).

---

## The port map (v4 mockup element → real `hive.html` binding — REUSE existing data/functions)

| v4 element | Wire to (reuse, don't reinvent) |
|---|---|
| Hero "3 things need you" — 3 action tiles (red/amber/accent) | the SAME live sources the current cards read: **PM overdue** (the "PM Tasks Overdue: 6 assets" source), **low stock** (the "Stock Alert: 3 items" source), **your open jobs** (the "3 open jobs → logbook" source). Order by urgency; overdue = "Safety · do first" peak. |
| "Since your last shift" ribbon | compute deltas from existing feed/activity (jobs closed, readiness Δ, new alerts, last-sync time). If a delta isn't cheaply available, ship the ones that are + omit the rest (honest, L1). |
| Readiness goal-gradient stairs "67/100 · 33 pts → Stair 2" + weakest dim | the existing readiness/stair calc (Process/Data/Resilience/Leadership/Culture); replace the 5 rainbow bars with one length-bar + trend + weakest/strongest callout (E1: length not gauge). |
| Today's brief (AI) | existing AI-brief source, tightened copy (kill the meta prose). |
| 11 open WO · 3 on-shift · Setup 80% | existing counts; setup reframed "1 step → badge" (H2). |
| Quiet links (Pattern alerts / Hive activity / Roster) | existing collapsed sections (progressive disclosure, A3). |
| **First-run empty state** | the NEW-hive path: when the board has no data yet, render the value-first "log your first job" view (O1) instead of the cramped Get-Started checklist. Reuse the real first-entry form/flow; labels-above + inline validation (M1/M2). |

---

## Constraints & gates (do not regress)

- **Live, not static.** Every number binds to the real source; empty/loading/error states handled
  (skeletons per D2/E2; honest empty per O1).
- **Mobile-first + responsive** (F1: ≥44-48px targets, thumb-zone sticky primary action, stacked tiles).
- **Accessibility** (C2/F2/Q1): WCAG contrast 4.5:1 text / 3:1 UI; visible focus; `prefers-reduced-motion`
  variant; run **axe = 0**.
- **escHtml / XSS** (security skill): every interpolated string escaped; `escHtml` defined per-file.
- **Hive gate + role** (multitenant): supervisor vs worker views correct; hive isolation intact.
- **Render-budget ratchet**: `hive.html` is already ~271KB — the `render-budget` gate is a ratchet. Keep
  the net add lean (reuse existing CSS/tokens/components.css; don't inline a second design system).
- **Canonical registry / new-feature checklist** if any new page/section is registered.
- **Gates green**: `python run_platform_checks.py --fast` (+ the hive/render-budget/canonical gates);
  after any substrate-affecting edit, `python tools/build_substrate.py` + `night_crawler.py --reindex`.

## i18n Tagalog toggle — SCOPE CAREFULLY (likely Phase 2)
The v4 EN/FIL toggle is a genuine feature, not just CSS. Check whether the platform already has an i18n
system; if not, the toggle is net-new infra (a string catalog + a locale switch) — **descope to a Phase-2
stretch** and ship the core redesign first (N1's real deliverable here = *don't hardcode-break on long
strings* + leave the layout expansion-tolerant, which the mockup already proves).

---

## Verification (live, before calling it done)

1. **Live Playwright walk** (reuse the Mega Gate / `reference_live_dbclient_roundtrip_method`): supervisor
   + worker, on a **new (empty) hive** AND a **worked hive**. The empty hive shows the first-run view; the
   worked hive shows the 3-tile board.
2. **5-second re-test** (A1): screenshot → a stranger states purpose + primary action in ≤5s.
3. **axe = 0** (WCAG2.2-AA); contrast spot-checks (C2); `prefers-reduced-motion` honored (Q1).
4. **Mobile 430** + desktop 1440 both correct (F1); tap targets ≥44px.
5. **Re-screenshot the REAL page** before/after → drop into the Desktop folder as the "shipped" proof.
6. **Gates**: `run_platform_checks.py --fast` green; render-budget not regressed.

---

## ⚠ CURRENT → TARGET DISPOSITION MAP (the artifact the arc was MISSING — added 2026-07-15)

Root cause of the v4 slop: the port map above was ADDITIVE (mockup→data), never a brownfield
transformation. Built from the LIVE inventory of `#view-board`'s 28 children. A redesign = execute
EVERY row, especially DELETE/MERGE. Verify with a FULL-PAGE screenshot, not viewport-only.

| # | Real element | v4 disposition |
|---|---|---|
| 1 | board header (conn dot, hive-name, ⋯More) | **KEEP** — the v4 top bar |
| 2 | `#code-strip` (hidden toggle) | KEEP |
| 3 | `#supervisor-summary` (greeting+tiles+action+readiness) | **DONE** = v4 hero |
| 4 | presence bar `.mb-4` "On Shift Now" (116px) | **MERGE** → a compact "N on shift" mini-stat (demote the big bar) |
| 5 | `#my-work-card` (worker-only) | KEEP (worker path) |
| 6 | `#hive-focus-chip` (conditional) | KEEP |
| 7 | stats row (`#stat-open` "Open WO" + `#stat-members`) | **MERGE** → v4 mini-stats card. Both ids stay VISIBLE (test-locked: journey-cross-page + kpi-parity). `#stat-open` (11) also = jobs tile → mini-stat framing, not a big standalone card |
| 8 | `#board-source-chip` (62px) | **DEMOTE** to bottom (test-locked visible: journey-hive:284) |
| 9 | `#health-details` (readiness 5-dim, collapsed for supervisor) | KEEP collapsed = drill-down under my readiness glance (no visible dup when collapsed) |
| 10 | `#onboarding-card` "Get started 80%" (223px) | **COMPACT** → slim "Setup 80%" line |
| 11 | `#adoption-card` (hidden/conditional) | KEEP |
| 12 | **`#pm-overdue-alert`** "6 assets overdue" (117px) | **DELETE-for-supervisor** (redundant with red PM tile); keep for worker |
| 13 | **`#stock-alert`** "3 items low" (117px) | **DELETE-for-supervisor** (redundant with amber stock tile); keep for worker (personal) |
| 14 | `#team-stock-alert` (hidden/conditional) | KEEP |
| 15 | `#todays-brief-panel` (AI, 124px) | **MOVE** → LEFT column |
| 16 | `#reliability-coach-panel` (68px) | **MOVE** → LEFT column (under brief) |
| 17 | `#benchmark-panel` (hidden collapsed) | MOVE → quiet links |
| 18 | `#pattern-alerts-panel` (collapsed) | MOVE → quiet links |
| 19 | roster `<details>` (collapsed) | MOVE → quiet links |
| 20-28 | handover, handover-sheet, team-pulse, approval-queue, audit-log, intent-capture modal, misc script/style | KEEP (conditional supervisor tools + modals; not in the mockup, appear on demand) |
| + | **NEW** foot reassurance "✓ You're on top of the hive" | **ADD** (v4 `.foot`) |

**Execution order:** (A) DELETE-for-supervisor 12+13 [kills the visible duplication] → (B) two-column grid: LEFT 15+16, RIGHT compact mini-stats from 4+7+10 → (C) quiet-links row 17+18+19 → (D) foot → (E) full-page screenshot vs mockup → (F) fix the 2 journey-hive tests (missed ss-issues-hero:326 + board-source-chip flake) → (G) gates + substrate rebuild.

## PROGRESS (measured, updated per phase)

- **Phase 2a — v4 action-first hero: ✅ DONE + live-verified (2026-07-14).**
  - `#ss-verdict` repurposed as the greeting headline **"Good {tod}, {name} — N things need you"** (A1 5-second focal point); first-run → "Welcome, let's set up your hive"; all-clear → "you're all clear". Tone icon (✓/!/⚠/·, SVG-converted by whIconSystem) preserved.
  - The 3 `#ss-cards` transformed into **v4 action tiles**: PM overdue (red + "Safety · do first" peak, → pm-scheduler), low stock (amber, → inventory), open work (blue, → logbook). Data source unchanged (overdue/lowStock/openWO); presentation is now action-first. Deep-links via real `<a href>` (keyboard-accessible). rag-tiles: hive:pm_overdue / hive:low_stock / hive:open_work.
  - Live-verified on **desktop (1036px)** + **mobile (390px, dpr 1.0)**: greeting + 3 tiles render with real data (6 overdue / 3 low / 11 WO), 0 console errors, horizontalScroll=0, tiles stack full-width on mobile with ≥44px targets.
  - **CLS-safe:** reserves re-measured — `#supervisor-summary` 618→460px, `#ss-cards` 318→160px, `align-items:start` stops tile-stretch; value identical in `.hidden`/`:not(.hidden)` = zero CLS on un-hide.
  - **Gates green:** `validate_hive_board.py` PASS, `validate_rag_flywheel_locks.py` PASS (old hive tile-locks retired w/ dated note, matching the predictive precedent). Tests repointed to the new contract: `journey-hive.spec.ts` (3 tiles + labels + icon-system-robust), `journey-cross-page.spec.ts` (open-work tile ↔ stat-open). `--fast` in flight.
  - Reduced-motion: `@media (prefers-reduced-motion: reduce)` kills tile transitions. No second design system (reused `--wh-*` + file's semantic colors).

## NEXT (remaining v4 slices — measured queue)

`NEXT: (1) readiness goal-gradient (H1) — promote a compact "composite/100 · Stair N · weakest dim" line into the fold using EXISTING _lastReadiness (no new query). (2) since-last-shift ribbon — HONEST cheap deltas only (jobs-closed-today + unread-alerts + live-sync); "last shift" has no WorkHive shift-boundary, so reframe as "today" not a fake shift delta (L1). (3) first-run value-first form — the dedicated log-first-job view on the isFirstRun path (greeting already handles the headline). (4) mobile sticky action — DESCOPE candidate: redundant with the red PM tile + risks the documented bottom-right FAB collision. (5) i18n EN/FIL — Phase-2 stretch, no infra → descope. Then: full journey-hive/cross-page run, axe=0, provenance/render-surface regen, skills+memory synthesis. Ian-gated: commit + deploy.`

## NEXT (fresh window starts here)

`NEXT: Phase 1 — Understand hive.html (map the board render fn, its live data sources, the first-run path,
the CSS/token system, existing i18n?). Phase 2 — implement the above-the-fold v4 board (hero 3-tiles wired
to real PM-overdue/low-stock/open-jobs, readiness goal-gradient, tightened brief, progressive-disclosed
secondary) + reduced-motion + a11y; verify live + axe. Phase 3 — first-run empty-state view (value-first
log-first-job, proper form) on the new-hive path; verify live. Phase 4 — mobile pass + sticky action;
re-screenshot real before/after. Phase 5 — gate-lock (render-budget, hive, canonical) + skill/memory
synthesis. i18n toggle = Phase 2-stretch only if infra exists. GROUND FIRST: read
substrate/reference/ufai-ux-rubric.md + the two _MOCKUP_v4_*.html on the Desktop + skills
frontend/designer/mobile-maestro/qa/multitenant/performance. Reuse, don't reinvent. Ian-gated: commit +
deploy are his.`
