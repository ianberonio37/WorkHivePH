# Battery Coverage Ledger — the live-sweep campaign tracker

> Companion to `BATTERY_ROADMAP.md` §7. Tracks `(page × altitude × role/state)`
> across turns. **A blank is an admission, not a pass.** Marks: `—` not started ·
> `R` referee-clean (0 Major) · `S` swept-all-states · `✓` role-matrix complete ·
> `FP` flagged-then-confirmed-false-positive.

## Per-page live-sweep protocol (run this for every page)

1. `browser_navigate` → `http://127.0.0.1:5000/workhive/<page>.html`
2. install + boot: `fetch('ufai_battery.js')` (relative — served at `/workhive/`,
   NOT `/`) → `(0,eval)(t)()` → `await __UFAI.boot()`.
3. **Resize to a TRUE mobile viewport BEFORE reading tap-targets.** This MCP
   browser runs at **dpr 0.8**, so `resize(390)` gives CSS-width 487 (tablet) and
   `resize(312)` gives the real **CSS 390**. Tap-target<44 is a MOBILE rule —
   reading it at desktop width false-flags desktop nav links (mouse targets that
   `display:none` on mobile). Always confirm a tap flag at CSS-390 before fixing.
4. `await __UFAI.run({pageId, role, experience})` → triage:
   - **DEFECT (referee)** → fix inline (then `delete window.__UFAI` + re-install if
     the battery file changed).
   - **TASTE/IA (critic)** → `__UFAI.critic` candidates → `ufai_ingest.py`.
5. `__UFAI.sweepAll()` for multi-state (tabs/toggles); open modals manually.
6. Role×experience: re-seed identity, reload, re-run (dashboard pages need auth).
7. Log the row below.

**Known noise to ignore:** `favicon.ico` 404 (no favicon on the Flask bridge) ·
my own probe 404s · desktop-width tap-target flags (see step 3).

## Environment preflight (once per session)

`curl :5000/workhive/index.html` → 200 · `curl :54321/rest/v1/` → 200 ·
`curl :54321/auth/v1/health` → 200. If `sign-in failed:{}` → check auth health
first (DevOps: the empty-error fingerprint = GoTrue unreachable, not credentials).

---

## ② Page altitude — the matrix

| Page (nav tier) | signed-out | field | supervisor | engineer | ① Comp | ③ Journey |
|---|---|---|---|---|---|---|
| **index** (Home) | **R** (signed-out landing clean; desktop-nav tap = `FP`) | **R**✅ (dashboard) | **R**✅ (dashboard FIXED, see below) | n/a | — | — |
| logbook (Field) | n/a | **R** ✅✅ (B1: 25× CSS muted 0.3/0.35→0.6. **B4b worker EMPTY state: `.empty-state{opacity:0.4}` parent-opacity trap → text/60 effective 0.24=2.2:1; fixed opacity→1 + Tailwind text-white/40&/25→/60; axe 0 verified empty**) | — | n/a | — | — |
| inventory (Field) | n/a | **R** ✅ (B1: 0 Major. **B4b: SAME `.empty-state{opacity:0.4}` trap fixed (opacity→1 + /40&/25→/60); empty-state forced-visible axe 0**; CLS needs-improvement Minor) | — | n/a | — | low_stock |
| dayplanner (Field) | n/a | **R** (0 Major; CLS 0.34 POOR = known-deferred Minor) | — | n/a | — | overdue |
| pm-scheduler (Team) | n/a | **R\*** (1 Major queued: FAB occluded by global Online chip → `sweep:shell:fab-occluded-by-conn-chip`, cross-cutting) | — | n/a | — | overdue |
| hive (Team) | n/a | n/a | **S**✅ (FIXED 6 `.ic-opt` labels +1 "View Inventory" →44px tap; 0 Major; CLS 0.67 poor deferred) | n/a | — | — |
| community (Team) | — | — | **R\*** (1 Major = FAB `#fab-post` occluded by `#wh-hub-fab` = same queued shell class) | — | — | — |
| analytics (Intel) | n/a | n/a | **S** (0 Major across 6 states/4 phase-tabs; LCP poor Minor) | — | — | — |
| predictive (Intel·hidden) | n/a | n/a | **S** (0 Major; LCP+CLS poor Minor) | — | — | risk |
| asset-hub (Intel) | n/a | n/a | **S** (0 Major default+toggles; CLS poor; detail-drill deferred) | — | — | risk/approvals |
| alert-hub (Intel) | n/a | n/a | **S**✅ (0 Major across **10 states**/8 tabs; CWV good) | n/a | — | risk |
| shift-brain (Intel·hidden) | n/a | — | **S** (0 Major; CLS needs-improvement Minor) | — | — | — |
| ph-intelligence (Intel·hidden) | n/a | n/a | **R** (0 Major; CLS 0.182 needs-improv Minor; 1 console 404=data-fetch, wiring intact) | — | — | — |
| assistant (Intel) | — | — | **R**✅ (FIXED 4 Major tap: back/Setup 20px, New-Chat 16px, Chat & Journal tabs 30px →44; send-btn 42→44; New-Chat white/30→white/60. 0 Major across 3 states. CLS 0.818 deferred.) | — | — | — |
| voice-journal (Intel·hidden) | n/a | — | **R**✅ (PRISTINE — 0 defects, CWV all good) | — | — | — |
| ai-quality (Intel·hidden) | n/a | n/a | **S**✅ (0 defects, CWV good; About-disclosure state clean) | n/a | — | — |
| audit-log (Intel·hidden) | n/a | n/a | **S**✅ (FIXED `--muted` token 0.4→0.6 = 3 contrast nodes; `.chip` 32→44, btn-export/btn-clear/filter-input 40→44, Load-More →44; 0 Major across 6 states; CWV good) | n/a | — | — |
| analytics-report (Intel·hidden) | n/a | n/a | **S**✅ (FIXED `.ar-header p` #7B8794→#9AA8B6, `.toolbar-label` 0.35→0.6, `.pill-btn` 0.55→0.7 + active purple #a78bfa→#c4b5fd + 36→44, `.btn-action` 40→44; 0 Major across 2 states) | — | — | — |
| plant-connections (Ops·hidden) | n/a | n/a | **S**✅ (FIXED `--muted` token 0.4→0.6 = 5 contrast nodes incl `.sc-label`; 0 Major across 2 states; CWV good) | n/a | — | — |
| engineering-design (Build) | n/a | n/a | n/a | **S**✅ (FIXED endemic muted-text: ~40 inline + CSS `rgba(255,255,255,0.4/0.3/0.25)`→0.6; `.page-tab`+`.recent-chip`→44px tap; 0 Major at LOAD **and** in deep discipline→calc-type flow. CLS 0.932 deferred. Placeholders/deco-icon 0.3 left.) | — | — |
| project-manager (Build) | n/a | n/a | **S**✅ (FIXED 3 red-chip contrast `.ptype-shutdown`/`.status-cancelled`/`.phase-gate` + `button.danger` → `#F58A89`; base `button` min-height:44 flex-center → 2 tap Minors gone. 0 Major across **7 states** + New-project & detail modals. CLS 0.109 deferred. Note: `project-progress` edge fn 404 = env gap, page degrades.) | engineer ↓ | — | — |
| project-report (Build·hidden) | n/a | n/a | **R**✅ (FIXED `.toolbar button/.btn` 39.3→44 tap [Back/AI-Narrative/Print/Save-PDF]; 0 Major; CWV good. "Go to PM" = inline-link exempt) | — | — | — |
| skillmatrix (Grow) | — | ✓(W2) | ✓(W2) | ✓(W2) | — | — |
| resume (Grow) | — | — | **R**✅ (FIXED 1 `.page-header p` contrast #7B8794→#9AA8B6; input-font<16 Minor = checkbox FP, not a text field; CWV all good) | — | — | — |
| achievements (Grow) | — | — | **R**✅ (FIXED 4 `.pillar-title` contrast 0.35→0.6; 0 Major across 2 toggle states; CLS 0.703 poor = deferred Minor) | — | — | — |
| marketplace (Connect) | — | — | **R\*** (battery flagged dead `onclick="handleSellerOnboard()"`; my window-expose fix REVERTED — platform is FREE/no-Stripe, so the Connect-Stripe path is vestigial → queued `sweep:marketplace:vestigial-stripe-ui` to REMOVE. Otherwise 0 Major across 5 states.) | — | — | — |
| report-sender (Connect·hidden) | n/a | n/a | **R**✅ (FIXED `.add-contact-btn` 27.9→44 + `.install-icon-btn` 34→44 tap; `.contacts-empty` 0.28→0.6 latent empty-state contrast; 0 Major) | n/a | — | — |
| integrations (Connect) | n/a | n/a | **S**✅ (2 Major→0: `--muted` token + 2 inline tabs + JS inactive-tab 0.4→0.6; 4 `.step-label` stepper 0.2/0.5→0.6/0.85; Dismiss btn + 3 guide CTAs + 3 main tabs →44px tap. 0 Major across 2 states + forced-guide first-visit state. CLS-on-state-change deferred.) | n/a | — | — |

## ① Component altitude
Static `survey_component_consistency.py`: **52 .simple-card + 8 .sum-card, 0 drift** (clean).
Live `__UFAI.component()` **CONFIRMED ✅** — analytics (.simple-card ×3, 1 shape, 0 drift) +
predictive (.simple-card ×3 shape[sc-hero,sc-label,sc-sub,sc-tag] + .sum-card ×4 shape[sl,sn],
both 1 distinct shape, 0 defects/0 major). Both primitives proven intra-page consistent live;
matches the static cross-page survey.

## ③ Journey altitude — **EXECUTED LIVE ✅** (`journey_battery.js`/`__JOURNEY`, supervisor)
| Journey | Path | KPI | Verdict | Note |
|---|---|---|---|---|
| Due/overdue | pm-scheduler→dayplanner | overdue | **DRIFT 2 vs 3 (Major)** | REAL finding — same-NAMED≠same-DERIVATION (2 per-ASSET v_pm_compliance_truth vs 3 per-SCOPE-ITEM; both correct). Visible `.sc-label`="Overdue" on both hides the unit → confusing. Ingested `sweep:ia:relabel:overdue-asset-vs-task` (RELABEL, don't fix math). |
| Highest-risk | predictive→asset-hub→alert-hub | at_risk | agree (0/0/—) | risk lenses consistent (hive has no high-risk now; `—` handled as no-value). |
| Pending-approval | asset-hub→inventory | pending_approval | agree (0/0) | COINCIDENTAL zero (plan expected drift-confirms-distinct; both empty so can't prove — no defect, correct). |

**Journey limitation found:** identity seam `window.WHShell` is ABSENT on these pages → `verdict()`
asserts NUMBER-continuity only, not STATE-continuity (identity constant). Journey battery needs a
localStorage identity fallback to assert state-continuity. → ai-engineer/frontend writeback.

## ④ Platform altitude — IA-streamlining / redundancy-type surveyor RE-RUN ✅ (2026-06-08; Ian caught I'd skipped it in the campaign claim)
`run_battery_family.py --gate` 🟢 at baseline (11→ candidates, 0 missing-required).
11 IA candidates **disposed** (Phase A): 1 approved / 3 deferred / 7 rejected.

**Streamlining redundancy surveyor (the piece I had silently dropped from the "full battery") — now run end-to-end:**
- **Layer A LIVE** — `__UFAI.inventory()` captured live on 5 actionable-theme pages → `.tmp/ia_inventory/*.json` (pm-scheduler/dayplanner/project-manager/asset-hub/inventory). Pages are **fully tagged EXCEPT asset-hub**, which carries **4 `kpi-untagged` units** ("Logbook entries"/"PM completed"/"Last failure"/"Edges") the STATIC parse is blind to — the live layer's real payoff. (Governance note: untagged KPIs escape `validate_user_facing_kpi_canonical.py`'s 0-math-drift contract — candidate to tag them, or accept as per-asset detail stats. → data-engineer/architect.)
- **Layer B** — `survey_ia_redundancy.py` static+live merge → **28 pages / 87 info-units** (was 83; +4 = the untagged asset-hub KPIs). R1 1 exact-label/2 same-key/6 themes · R2 8 affordances · R3 detail_panel×15.
- **Phase 2** — `score_ia_streamlining.py` → **14 scored, 11 queued**: **1× RELABEL** (`Pending approval` asset-hub-assets vs inventory-parts, Major — caught STRUCTURALLY where journey-3 saw only coincidental 0/0), **4× DIFFERENTIATE/merge-review** (risk/hot/critical · due-soon · healthy/on-track · **late/overdue** = the static theme-cluster of the journey-1 drift), **6× REVIEW** affordance paths, 3× KEEP. All idempotently already in `sweep_critiques.json` (0 new).
- **Corroboration:** the journey's value-drift evidence (overdue 2 assets vs 3 tasks; pending 0/0) + the static surveyor's structural types are COMPLEMENTARY — the journey proves derivation-distinctness with live values, the surveyor catches same-label/same-subject even when values coincide. The overdue candidate `sweep:ia:relabel:overdue-asset-vs-task` is the live-grounded sibling of static `sweep:ia:theme:late-overdue`.

---

## Progress log

- **2026-06-08 · Phase A** — platform baseline frozen (`battery_family_baseline.json`,
  candidates=11); disposed all 11 IA candidates.
- **2026-06-08 · Phase B1 · index** — signed-out landing referee-clean at CSS-390
  (tap/axe/overflow/focus all 0, CWV LCP 2.1s/CLS 0.04 good). Desktop-nav tap<44 =
  confirmed FALSE POSITIVE (mouse targets hidden on mobile). **Established the live
  loop + the dpr-390 protocol.**
- **2026-06-08 · Phase B1 field-core (as worker Bryan, hive b0c61993, CSS-390):**
  - **logbook** — FIXED: 25 muted-text `color:rgba(255,255,255,0.3/0.35)` → `0.6`
    (axe color-contrast on `#logbook-count-label` + 24 latent siblings). Re-verified
    axe 0 / major 0.
  - **inventory** — R, 0 Major (CLS needs-improvement = Minor, late-content shift).
  - **dayplanner** — R, 0 Major (CLS 0.34 POOR = known-deferred layout-shift Minor).
  - **pm-scheduler** — 1 Major SURFACED+QUEUED (not fixed — cross-cutting):
    `sweep:shell:fab-occluded-by-conn-chip`. The global `#wh-conn-chip` ("Online",
    z:9998) overlaps the page `.fab` (z:20) → axe target-size serious. Needs a
    shell-cluster stacking contract, not a one-page reposition.
  - **Next:** B2 supervisor-intelligence (sign in as supervisor Leandro): hive,
    analytics, predictive, asset-hub, alert-hub, shift-brain. Then index signed-in
    dashboard (field + supervisor).
- **2026-06-08 · Phase B2 supervisor-intelligence + index dashboard (as supervisor
  Leandro `leandromarquez`, hive b0c61993, CSS-390, run+sweepAll DEEP multi-state):**
  - **hive** — FIXED: 6 `.ic-opt` radio labels `min-height:44px` + "View Inventory →"
    link →44px inline-flex tap. Re-verified 0 Major / tap 0. (CLS 0.67 poor deferred.)
  - **analytics** — S, 0 Major across **6 states** (4 phase tabs + expand). LCP poor Minor.
  - **predictive / asset-hub / shift-brain** — S, 0 Major (CLS/LCP poor = known Minors).
  - **alert-hub** — S, 0 Major across **10 states** (8 tabs). CWV good.
  - **index signed-in dashboard** — FIXED: the deep sweep's "expand:More" state caught
    what default missed — **19 axe contrast nodes** (`.oh-card` muted whites 0.3/0.35/0.4
    →0.6, 19 declarations) + **3 tap structures** (`.oh-job-row` min-height:44 + the `→`
    arrow link →44×44 (template fix = all 5 rows) + "All assets →" →44px). Default now
    0 Major/tap 0/axe 0. Residual: a transient 4-node contrast on an `a[href="#"]`
    handler-link in the More-expanded sub-state (not reproducible in a stable render — noted).
  - **PROOF the deep half matters:** index default was clean BUT the expanded Operations
    Hub had 22 real defects — a default-only sweep would have falsely passed it.
  - **Next:** B3 build/grow/connect + B4 hidden long-tail (engineering-design,
    project-manager, skillmatrix, resume, achievements, marketplace, integrations,
    community, ph-intelligence, assistant, voice-journal, ai-quality, audit-log,
    plant-connections, report-sender, analytics-report, project-report). Worker-role
    pass on the field-visible pages too.
- **2026-06-08 · Phase B3 (in progress, supervisor Leandro, CSS-390, run+sweepAll):**
  - **community** — R\*, 1 Major = FAB `#fab-post` occluded by `#wh-hub-fab` = the SAME
    cross-cutting shell class already queued (`sweep:shell:fab-occluded-by-conn-chip`;
    confirms TWO shell occluders: `#wh-conn-chip` higher + `#wh-hub-fab` lower → page
    FABs at any `bottom` hit one). CLS poor; 7 modal-triggers = deferred deep-drill.
  - **marketplace** — battery flagged dead `onclick="handleSellerOnboard()"` ("Connect Stripe
    to receive payments"). I first exposed the fn on `window` — but **REVERTED**: the platform
    is FREE / no Stripe ([[project-free-platform-no-stripe]]), so activating a Stripe Connect
    onboarding flow is WRONG. The button no-ops again (harmless); the vestigial Stripe path is
    queued for REMOVAL (`sweep:marketplace:vestigial-stripe-ui`). **Lesson: a battery DEFECT
    needs product-context before picking the fix direction — dead payments button = remove,
    not activate.** Otherwise 0 Major across 5 states.
  - **achievements** — FIXED 4× `.pillar-title` contrast 0.35→0.6. 0 Major (2 toggle states). CLS 0.703 deferred.
  - **resume** — FIXED 1× `.page-header p` #7B8794→#9AA8B6. CWV all good. (input-font<16 Minor = the `#promote-dedupe` checkbox, NOT a text field → battery FP; checkboxes don't trigger iOS zoom.)
  - **integrations** — 2 Major→0. The systemic contrast fix was the `--muted` token (0.4→0.6, drove most of 12 nodes) + 2 inline inactive-tab colors + the JS that re-applies inactive-tab color on switch (else a tab-switch regresses it). Stepper `.step-label` 0.2/0.5→0.6/0.85 (kept hierarchy). Tap: Dismiss 18px→44, 3 guide CTAs 30px→44, 3 main tabs 42.5px→44. **Forcing `#cmms-guide` display:block (first-visit state, normally JS-gated) exposed the step cards' own defects — a default sweep would have missed the whole guide.**
  - **project-manager** — 1 Major→0 + modal Major→0. Red-on-faint-red chips (`.ptype-shutdown`/`.status-cancelled`/`.phase-gate`) + `button.danger` "Delete" all used brand red `#E15554` (~3.7–4.5:1) → lightened to `#F58A89` (chip-red, ~6:1, keeps danger identity). Tap: base `button` got `min-height:44px;display:inline-flex;…` → cleared both 40/42px Minors across **all 7 states** (5 tabs+expand) + New-project & detail modals. CLS 0.109 deferred. **The `.danger`/`.phase-gate` reds only render inside the detail modal — caught by MCP-driving the card open, not by the page-load sweep.** Note: `project-progress` edge fn 404 locally (env gap; page degrades gracefully — DevOps).
  - **LESSON (red-on-faint-red chip pattern):** a colored chip whose TEXT and 0.18-alpha BG share the same hue fails AA when the hue is dark (red #E15554). Brighten the TEXT to a light tint of the hue (#F58A89), leave the bg tint. Blue/gold/green chips pass as-is (brighter hues). → designer + qa skills.
- **2026-06-08 · Phase B3 ENGINEER pass + B4 hidden long-tail (COMPLETE — 10 pages):**
  - **engineering-design** (engineer) — endemic muted-text: ~40 inline + CSS `rgba(255,255,255,0.4/0.3/0.25)`→0.6, `.page-tab`+`.recent-chip`→44px. 0 Major at load AND in deep discipline→calc flow (deep-sweep caught a 2nd wave: `.calc-subcat-header` 0.25, `.recent-chip` chip). CLS 0.932 deferred. **Placeholders/deco-icon 0.3 left intentionally (bumping a placeholder makes it look filled).**
  - **assistant** — 4 Major tap (Tailwind page): back/Setup 20px, New-Chat 16px, Chat/Journal tabs 30px →44 (inline min-height, JIT-safe); send-btn 42→44. New-Chat white/30→white/60. 0 Major / 3 states.
  - **voice-journal** — PRISTINE (0 defects).
  - **ai-quality** — clean (0 defects).
  - **audit-log** — `--muted` token 0.4→0.6 (3 nodes) + chip/export/clear/filter/Load-More →44. 0 Major / 6 states.
  - **plant-connections** — `--muted` token 0.4→0.6 (5 nodes incl `.sc-label` — this page MISSED the earlier 16-dashboard `.sc-label` fix). 0 Major / 2 states.
  - **report-sender** — `.add-contact-btn` 27.9→44 + `.install-icon-btn` 34→44; `.contacts-empty` 0.28→0.6 (latent). 0 Major.
  - **analytics-report** — `.ar-header p` #7B8794→#9AA8B6 (same hue as resume), `.toolbar-label` 0.35→0.6, `.pill-btn` 0.55→0.7 + active **purple-on-purple-tint** #a78bfa→#c4b5fd + 36→44, `.btn-action` 40→44. 0 Major / 2 states.
  - **project-report** — `.toolbar button/.btn` 39.3→44. 0 Major. (inline "Go to PM" link = exempt.)
  - **ph-intelligence** — clean (CLS 0.182 Minor; console 404 = data-fetch, wiring intact).
  - **LESSON (token-first contrast fix):** when a page has a `--muted` token, bumping the token (0.4→0.6) fixes ALL its muted-text contrast nodes in one edit (page-sub/sc-label/filter-summary/table-th). When it's inline literals (engineering-design), a scoped global replace is the equivalent — anchor on `0.4)` so `0.45)` is untouched, and EXEMPT `::placeholder` (bumping it reads as a filled value). → frontend + designer + qa.
  - **LESSON (Tailwind-utility pages):** prefer inline `style="min-height:44px"` over `min-h-[44px]` utility — survives whether or not the page's Tailwind build is JIT/arbitrary-value-enabled.
- **2026-06-08 · Phase B4b WORKER-role pass (as worker Bryan, empty-hive context):**
  - **logbook (empty)** — **THE find of this pass.** Worker's empty hive shows the empty-state,
    which the B1 supervisor sweep never saw (supervisor's logbook had entries). axe flagged
    `text-white/60` at **2.2:1** — impossible by my math (≈6.7:1) until axe revealed fgColor
    `#4e5663` ≈ 0.24 alpha. Cause: **`#empty-state` ancestor has `opacity:0.4`, which multiplies
    into every descendant's text alpha** (0.6 × 0.4 = 0.24). A text-color fix CANNOT beat a parent
    opacity. Fixed `.empty-state{opacity:0.4}`→`1` (muting now in text colors) + Tailwind
    `text-white/40`&`/25`→`/60`. axe 0 verified live in the real empty state. **In-codebase
    precedent existed: `#team-prompt` already had inline `opacity:1` w/ a comment about this exact
    AA trap — but only that one instance was patched, not the root rule.**
  - **inventory** — SAME `.empty-state{opacity:0.4}` trap (grep found it shared across logbook+inventory
    only). Same fix; empty-state forced-visible → axe 0.
  - **dayplanner** — 0 Major (CLS poor deferred).
  - **pm-scheduler** — 1 Major = the KNOWN-QUEUED `sweep:shell:fab-occluded-by-conn-chip`
    (`.fab` occluded by global `#wh-conn-chip`). Cross-cutting shell-stacking; deferred since B1
    (a global-shell z-index/position change is too broad to land unattended). Now confirmed on
    pm-scheduler + community → **escalate to Ian: needs a shell-cluster stacking-contract decision.**
  - **LESSON (parent-opacity contrast trap):** a contrast fix on text COLOR fails if any ancestor
    has `opacity<1` — it composites into the text alpha and axe catches it. When axe reports a
    contrast far worse than the text color implies, walk the ancestor chain for `opacity`. Prefer
    muting via text COLOR, never container opacity. → frontend + designer + qa + mobile.
  - **LESSON (empty/zero-data states are role-gated):** a hive with no data shows empty states the
    populated supervisor view never renders → sweep every page once in an EMPTY context (or
    force-show `#empty-state`). The deep-state lesson extended to the DATA axis.
- **2026-06-08 · Phase ① component + ③ journey — DONE (see §① and §③ above).**
- **2026-06-08 · Phase B4c — PLATFORM-WIDE parent-opacity audit (follow-through on the trap):**
  Grepped every `*.html` for `opacity:0.[1-7]` + `opacity-[1-6]0`. Triage: the vast majority are
  LEGITIMATE — `:disabled` (WCAG-exempt), `@keyframes`/skeleton/pulse (transient), SVG icons +
  `pointer-events-none` background glow blobs (decorative), and `-test`/`-backup`/admin/founder/learn
  (non-core). The egregious parent-MULTIPLY trap was contained to logbook+inventory `.empty-state`
  (already fixed). **TWO more data-state-gated cases the live sweeps couldn't reach (the data never
  rendered), caught only by the STATIC grep:**
  - **engineering-design** calc-RESULT cards (lighting + fault-current calcs) — sub-values at
    `opacity:0.5` + labels at `opacity:0.6` on `#fff`/lighter-`#1F2E45` cards (white×0.5 ≈ 3.8:1 on
    the lighter card = fail). Converted to `color:rgba(255,255,255,0.72)` / `0.8` (mute via color
    not opacity; ≈7.3:1). 3 disabled-step cards (`opacity:0.5;pointer-events:none`) correctly LEFT
    (inert UI, WCAG-exempt). Page loads clean; lighting/fault-current calc flow not driven live
    (deterministic style swap, contrast verified by math).
  - **analytics** predictive-failure table — a SUSPECT `<tr>` got `opacity:0.6` ON TOP of cells
    already at `rgba(255,255,255,0.5/0.6)` → effective **0.30 (~2.5:1)**. Swapped the row-dim for an
    amber `background:rgba(247,162,27,0.06)` tint (the ⚠ icon + amber mtbf already signal "suspect",
    so no readability cost). Bumped the adjacent `last_failure` cell 0.5→0.6. Verified analytics
    default + predictive-phase 0 Major/0 axe (suspectRowCount=0 in this hive — confirms it's
    data-state-gated, exactly why the original S-sweep passed it).
  - **LESSON (auditing the trap is STATIC, not live):** because the trap is data-state-gated (renders
    only for outlier/empty/specific data a live sweep may never hit), the platform-wide audit is a
    `grep opacity:0.x` over source + triage (exempt `:disabled`/`@keyframes`/svg/`pointer-events-none`),
    NOT a battery re-run. → frontend + qa.
  - **Next:** 3 queued dispositions for Ian (FAB-occlusion, vestigial-stripe, overdue/pending RELABEL)
    + the asset-hub untagged-KPI tag-or-accept call; then commit + deploy (Ian).
