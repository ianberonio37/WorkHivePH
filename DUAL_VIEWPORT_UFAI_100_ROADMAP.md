# Dual-Viewport UFAI → 100% Roadmap

**Goal (Ian, 2026-07-18):** "fold it all to a roadmap and let's finish it all to 100% overall the full UFAI rubric" — drive every page of the family to 100% on the **dual-viewport** rubric (graded at BOTH 390 phone + 1280 desktop, worse-per-dim).

## The arc so far (DONE)
1. **Class T · Native-app feel (T1–T8)** — Night-Crawler harvest of React-Native + CSS standards → new cited class in `ufai-ux-rubric.md` + measured detectors in `survey_ufai_rubric.js` + battery v1.5.0. Verified live 35×8 = 0 fails.
2. **Native-feel applied family-wide** — `tokens.css` (touch-action:manipulation, overscroll-behavior:contain) + `utils.js` guarded fallback. T3+T4 → 100% family-wide.
3. **Dual-viewport grading** — `family_rubric_sweep.mjs` now grades viewport-sensitive dims (C1,C3,R\*,V\*,F1,K2,M1,W1,T\*) at 390+1280, worse-per-dim; content dims stay desktop (artifact-free). This is what "the rubric considers the phone" means.

## Current board — 32 pages · mean 99 · **17 pages with ≥1 gap**

## The gap list, categorized (don't chase phantoms — §16.1 "the ruler or the page?")

### A · RULER ARTIFACTS — fix the detector first (removes phantom gaps)
- **V1 [index, hive, engineering-design, public-feed] = 0% @390** — "widget covers header" is a **decorative full-viewport background** (`#cursor-glow`, `#aurora-scene`, z-index:0, pointer-events:none) geometrically overlapping the header but sitting BEHIND it. V1 must exclude z-behind / pointer-events:none / decorative backgrounds. → **Fix `survey_ufai_rubric.js` V1.** (pm-scheduler V1 = "bottom-nav × wh-hub" may be a REAL floating-widget collision — re-check after the detector fix.)

### B · SHARED FIXES (one change → many pages)
- **T8 [hive 85%, integrations 75%, agentic-rag-observability 0%]** — more stateful controls with no aria-state; extend `WH_TOGGLE_CLASSES` (utils.js) to their tab/toggle classes (same shared-layer fix as before).
- **R3 [marketplace 67%, community 67%, engineering-design 67%]** — control-vocabulary drift (one shape per control role); likely a shared token/class fix.

### C · PER-PAGE REAL FIXES
- **F1 [index 65%, voice-journal 79%]** — tap targets <44px @390.
- **K2 [index 50%, voice-journal 50%]** — field reach / glance @390.
- **B3 [project-manager 67%, voice-journal 33%]** — readability (sentence length ≤20 / grade ≤8).
- **C1 [hive 67% @390]** — visual hierarchy at phone width.
- **C2 [shift-brain 98%, project-report 96%]** — contrast near-miss (one stop below floor).
- **E3 [shift-brain 50%], A1 [marketplace-admin 75%], N1 [marketplace-admin 75%]** — singles.

### D · ENV / EXEMPT (verify, don't blindly "fix")
- **I1 [marketplace 50%, logbook 50%, ph-intelligence 50%]** — Core Web Vitals. Local dev LCP runs slower than prod (Tailwind CDN, unminified, local RPC); the harness note flags the 2500ms prod target vs 4000ms local bar. **Verify against PROD before treating as a real gap** — likely a local-env artifact.
- **promo-poster [R2 0%, T1 0%, T5 0%]** — a fixed-width PRINT poster; phone-layout dims don't apply. → mark **N/A** for the poster (like other print docs), not "fix".

## Drive queue (execute in order; re-sweep after each cluster)
1. ✅ **DONE — Ruler: V1** container-child + decorative-bg exclusion (`f4c9c2e`). index/hive/eng-design/public-feed phantoms cleared → 100%; pm-scheduler isolated as a REAL collision.
2. ✅ **DONE — T8** (committed local): action-verb exclusion (agentic-rag `#filter-apply` false positive → N/A) + wired hive/integrations toggles via `.wh-toggle`. hive 85→100, integrations 75→100, agentic-rag →N/A.
3. **NEXT — REAL per-page fixes remaining (≈8 clusters):**
   - **pm-scheduler V1** — real collision: bottom-nav bar × nav-hub FAB overlap @390 (reposition/clear).
   - **hive C1 67% @390** — visual hierarchy at phone width.
   - **R3 [marketplace 67%, community 67%, engineering-design 67%]** — control-vocabulary drift (one shape per role); likely a shared token/class fix.
   - **F1 [index 65%, voice-journal 79%] · K2 [index 50%, voice-journal 50%]** — tap size / field reach @390.
   - **B3 [project-manager 67%, voice-journal 33%]** — readability (≤20 words/sentence, grade ≤8).
   - **C2 [shift-brain 98%, project-report 96%]** — one contrast stop below floor.
   - **singles:** E3 [shift-brain 50%], A1 [marketplace-admin 75%], N1 [marketplace-admin 75%].
4. **I1 [marketplace, logbook, ph-intelligence] = CLS 0.102–0.123 (>0.1)** — CORRECTED: NOT a local-env/LCP artifact (LCP is 132–448ms OK); a REAL marginal layout-shift on `#wh-main-content`. Reserve space for late content to pull CLS <0.1 (likely one shared fix — same culprit on 2 pages).
5. **promo-poster [R2/T1/T5 = 0%]** — a fixed-width PRINT poster; the phone-layout dims don't apply → mark **N/A** (add to the print-doc exempt path), not "fix".
6. **Final full dual-viewport sweep → 100% (or documented N/A) on all 32 pages.**

**Progress:** board was 32 pages / mean 99 / 17 with gaps → after V1 ruler + T8: the 4 V1 phantoms + 3 T8 pages resolved. Instrument verifies LOCALLY (`family_rubric_sweep.mjs`, no deploy needed per cluster); push fixes to prod at the end.

_Instrument: `node tools/family_rubric_sweep.mjs [--page X]` (local seeder, pabloaguilar). Board: `family_rubric_scoreboard.json`._
