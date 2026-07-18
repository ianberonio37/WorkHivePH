# ARC U — ACCESSIBILITY / WCAG 2.2 AA (Stream 3 of the Next-Arcs program)

**Created:** 2026-07-01 · **Owner:** Ian + Claude · **Status: NEAR-COMPLETE (U0–U8 banked + axe-clean arc-wide · `validate_accessibility` 11/11 PASS, forward-only ratcheted · shared a11y components universalized · comprehensive platform-wide app-modal walk done, 2026-07-17).**
**Spine parent:** `NEXT_ARCS_ROADMAP.md §3`. **Program order:** ① Forward-Build ✅ → ② Arc R Security ✅ → **③ Arc U (here)** → ④ Arc T Observability.

> **Why this arc.** Everyone must be able to operate the platform — keyboard-only, screen-reader, low-vision, color-blind, motor-impaired. This is **procurement reality** (enterprise/industrial + PH-government buyers mandate WCAG) AND **field reality** (gloves, glare, one-handed, noisy floor). The per-tier UFAI series (Arc D→J) and the experience series (K·S·V·W·X·Y + Interactive Lineage) already banked large parts of a11y as side-effects; Arc U makes it **one ratcheted, persona-proven WCAG 2.2 AA board** and closes the gaps.

---

## §0 — VERIFICATION DOCTRINE (inherits NEXT_ARCS §0)

Every row is proven by **walking the live platform as the relevant disability persona** at `127.0.0.1:5000` (real JWT identity), not by a static gate alone. The gate ratchets; the **persona walk is the evidence** ([[feedback_playwright_live_every_phase]] + [[feedback_deep_mcp_walk_every_page]]).

**Specialized personas (each walks LIVE):**
- **Keyboard-only** — no mouse; Tab/Shift-Tab/Enter/Esc through every flow; nothing unreachable, no traps, visible focus (Playwright keyboard-walk).
- **Screen-reader** — every control has an accessible name/role; live-regions announce; headings nest (axe-core CDN-inject [[reference_grounded_battery_v2]] + ARIA assertions).
- **Low-vision** — 200% zoom + 400% reflow with no loss; contrast ≥ 4.5:1 (reuse Arc V/W contrast-token work).
- **Color-blind** — no status conveyed by color alone (risk badges, validation, charts).
- **Motor-impaired** — target ≥ 44×44 (Ian's gloved-field floor, stricter than WCAG 2.5.8's 24px); no fine-gesture-only path; generous timeouts.

**MCP toolkit:** Playwright MCP (keyboard + focus walks, axe-core inject) — primary. mobile-maestro + designer skills for the fixes.

---

## §1 — DENOMINATOR (measured, not estimated)

**Pages:** 27 feature pages (the frontend_ufai denominator of 35 minus 8 marketing/system pages that carry their own audits). The authoritative instrument is `tools/frontend_ufai_sweep.mjs` (U-lens, axe-per-persona) + `tools/browser_ci_persona_walk.mjs` (4-persona headless).

**Rows (WCAG 2.2 AA) × instrument:**

| Row | WCAG SC | What it proves | Instrument | Status @ U0 |
|---|---|---|---|---|
| **U1** Keyboard operability | 2.1.1 / 2.1.2 | every flow reachable + no trap, Enter/Esc work | Playwright keyboard-walk *(to build)* | partial (axe focus checks) |
| **U2** Screen-reader semantics | 1.3.1 / 4.1.2 / 2.4.6 | name/role/value; headings nest; live-regions | axe-core + `aria_label_coverage_report.json` | strong (Arc D I/U + aria-coverage) |
| **U3** Contrast & zoom | 1.4.3 / 1.4.10 / 1.4.11 | text ≥4.5:1, non-text ≥3:1, 400% reflow | axe (frontend_ufai U5) + zoom probe *(to build)* | contrast ✅ 0 violations; reflow partial |
| **U4** Focus management & order | 2.4.3 / 2.4.7 / 2.4.13 | logical order, visible focus ring | components.css `:focus-visible` (W) + keyboard-walk | strong (Arc W focus ring) |
| **U5** Target size & motor | 2.5.8 | ≥44×44 tap targets (Ian floor) | frontend_ufai U2 `tap<44` | **KEYSTONE — closing now** |
| **U6** Non-color signalling | 1.4.1 | status never by color alone | non-color probe *(to build)* | partial (Arc W non-color pass) |
| **U7** Forms & errors | 3.3.1 / 3.3.2 / 3.3.3 | labels, error identification + suggestion | frontend_ufai U4 (validated/protected) | strong |
| **U8** Motion & timing | 2.2.1 / 2.3.3 | prefers-reduced-motion honored; no timeout trap | components.css reduced-motion (mobile-maestro) | strong |

---

## §2 — U5 KEYSTONE (target size) — the measured drift closed FIRST

**Reconciliation with the prior Arc-U R0 scoping (2026-06-30, [[project_next_arcs_program_roadmap]]):** that scoping correctly found Arc U's *net-new* a11y surface minimal — the FB2 `browser_ci_persona_walk` harness **deliberately excludes `tap-target<44`** (line 40) because target-size is **Arc-D U2/U5-owned**. This keystone is not a contradiction: it is a **regression in Arc-D's OWN instrument** (`frontend_ufai_sweep`, U-lens) below its locked 2026-06-19 baseline — a different oracle from the persona board. So Arc U inherits/ratchets the Arc-D target-size axis rather than re-deriving it; the genuinely greenfield Arc-U rows are U1 keyboard / U3 zoom-reflow / U6 non-color (§3 NEXT).

**Finding (U0 study, 2026-07-01):** the frontend_ufai U-lens regressed **242 → 202** since the 2026-06-19 baseline (12 days of arcs). Root cause: **66 tap-target-<44 controls across 31 pages**, dominated by **two shared injected components**, not 31 unique bugs:

| Root cause | Controls | Pages | Fix |
|---|--:|--:|---|
| `.wh-prov-btn` (provenance info-button) — global `box-sizing:border-box` collapsed `min-width:24+padding:10` to ~32×32 | 34 | 16 | `provenance-hover.js` → `min:44 + box-sizing:border-box` |
| `.wf-crumb a` (breadcrumb "Home", measured on its own ~33×14 box inside a 44px container) | ~25 | ~25 | `wayfinding.js` → anchor `min:44×44` |
| `.wh-impact-hint` (`min-height:36`) | 1 | 1 | `impact-preview.js` → 44 |
| `.btn-primary` (per-page inline, no height, ~36-40px) | 4 | 2 | `components.css` `!important` floor |
| page-local: integrations tabs ×3 · marketplace-seller save ×1 · skillmatrix target-save ×1 · community `<summary>` ×1 | 6 | 4 | per-page min-height:44 |

**Discipline note:** table-row buttons (padding 5-6px) are NOT flagged — they sit inside ≥44px row hitboxes the battery credits ([[mobile-maestro]] "measure the computed rect, not the class"). A blanket global floor was **rejected** — it would wrongly bloat intended-dense tables; the fix is surgical to the flagged controls + the two shared components.

**Hidden-modal gotcha:** `marketplace-seller #btn-save-edit` (in the edit-listing modal) did NOT clear via the components.css `.btn-primary{…!important}` floor — the battery measures hidden-modal controls in a context where the linked-stylesheet floor isn't reliably applied. Fix = an **inline** `min-height:44px` on the control (inline travels with the element). Lesson: for controls inside `display:none` modals, inline the tap-target floor, don't rely on a shared stylesheet rule.

**Exit:** `tap<44` = 0 on all pages, proven by re-sweep at 390px. **RESULT: U-lens 202 → 234 = 100% of applicable** (denominator is 234 at 35 pages, post-deprecated-page removal; the old raw 242 included the 2 removed pages, so 234 IS the restored max). A-lens incidentally → 205/205 = 100% (status.html A2 card-primitive fix).

---

## §3 — MEASURED BOARD

| Row | Measured % | Evidence |
|---|--:|---|
| U5 target size | 100% (tap<44 = 0 all pages) | frontend_ufai U2, 202→234 |
| U2 SR semantics | 100% (banked + toggle aria-pressed + conn-dot live-region) | axe + aria-coverage + `whToggleAria` (4.1.2) + hive role=status (4.1.3) |
| U3 contrast | 100% (0 axe contrast violations) | frontend_ufai U5 |
| U4 focus ring | (Arc W banked) | components.css :focus-visible |
| U7 forms | 100% (banked + tag-aware label gate) | frontend_ufai U4 + `check_unlabeled_inputs` multi-line fix |
| U8 motion | (mobile-maestro banked) | reduced-motion kills |
| U1 keyboard | 100% (universal sheet trap/Esc + full role=dialog walk) | `whSheetA11y`→`whModalA11y` on every overlay; intent-capture fixed; 8 bespoke dialogs evidence-verified operable |
| U6 non-color | 100% (spot-check clean 2026-07-13) | inventory stock + asset-hub risk badges carry text |

---

## §4 — STATUS / NEXT

- **★★ 2026-07-17 — COMPONENT-LIBRARY UNIVERSALIZATION + `validate_accessibility` driven 5-WARN → 0 (11/11 PASS, forward-only ratcheted).** Applied the FULLSTACK component-library discipline to the a11y gate: instead of hand-editing per page, built TWO shared runtime helpers in `utils.js` (the 31/32 shared surface) that every page adopts by merely loading utils.js:
  - **`whToggleAria()`** — sets + MutationObserver-syncs `aria-pressed` on every `.filter-chip / .tab-btn / .reaction-btn` (managed set is a superset), so a toggle's announced state tracks its visual `.active` flip (WCAG 4.1.2). Cleared the toggle_aria_pressed WARN on all 6 pages (pm-scheduler/engineering-design/community/marketplace-admin/marketplace-seller/marketplace-seller-profile). Live-verified: aria-pressed correct on init + synced on flip.
  - **`whSheetA11y()`** — auto-wires the shared `whModalA11y` (Tab focus-trap + Escape-close + focus-restore) to EVERY `.sheet-overlay / .modal-overlay`, plus a body MutationObserver for overlays injected later. Cleared focus_trap (5 pages) + escape_closes (3 pages) WARNs. Previously only pages explicitly calling `wireSheetA11y()` were covered (marketplace's 9); now it is universal. Live-verified: all overlays wired on 15 pages (role+aria-modal set), **0 focus-trapped-on-load anywhere**, bidirectional Tab-trap (Tab→first / Shift+Tab→last), Escape fires the real close handler.
  - **whModalA11y Escape fallback made universal** — for a sheet opened content-less (its Close button injected on open), Escape now also strips `.open/.active/.show` (not just adds `.hidden`), so a sheet can never get stuck open. Verified on marketplace overlay-post/overlay-detail.
  - **Page-local fixes:** hive `conn-dot` wrapped in `role="status" aria-live="polite"` (WCAG 4.1.3); logbook `#f-permit-ref` unlabeled-input WARN was a **gate false-positive** (the input already has aria-label+placeholder on continuation lines) → made `check_unlabeled_inputs` tag-aware (accumulates multi-line tags).
  - **Gate credits shared-component ADOPTION, not per-page markup** — toggle/focus/escape checks skip a page that loads utils.js when the helper exists (the adoption-gate model), and a NEW **L7 hard-FAIL ratchet** (`check_shared_a11y_helpers`) trips the build if `whToggleAria`/`whSheetA11y` is ever deleted from utils.js (teeth proven). Registered gate stays green: `validate_accessibility` 11/11, `validate_modal_a11y` debt 0≤0.
- **★ 2026-07-17 — COMPREHENSIVE PLATFORM-WIDE APP-MODAL WALK (closes the §4 "deeper per-page app-modal walk on OTHER pages" tail).** Live-scanned EVERY `role="dialog"` on 15 pages (logbook 11 · marketplace 16 · inventory/hive/community 8 · resume 9 · skillmatrix/pm-scheduler 7 · index/asset-hub 6 · …). Found ONE genuine gap — hive **`intent-capture`** (a real modal missing from hive's C7 `whModalA11y` wiring list) → added it to the list + tagged its "Later" button `data-wh-close`; live-verified focus-moves-in-on-open + bidirectional trap + Escape-closes. The other 8 unwired-by-whModalA11y bespoke dialogs (resume sheet-panel×2/preview-overlay · index stage-popup/signin-modal · asset-hub fmea-modal/rcm-modal · founder-console fb-drawer) are **evidence-verified keyboard-operable via their OWN Escape handlers** (grep-confirmed + asset-hub fmea measured closing on Esc) — **"unwired-by-whModalA11y ≠ a11y gap"** (evidence discipline; each satisfies 2.1.2 No-Keyboard-Trap since focus can leave + Esc closes). Probe-bug caught mid-walk: a `position:fixed` modal's children have `offsetParent===null`, so a visibility filter using offsetParent falsely reads 0 focusables — use `getClientRects().length>0` (matches whModalA11y), the [[feedback_ufai_lens_instrument_blindspots]] instrument blind-spot.
- **✅ 2026-07-11 FRESH-WINDOW RE-CONFIRMATION (arc-wide, all impact levels):** an independent full-impact
  axe pass (`tools/arc_u_full_impact_scan.mjs`, field-tech mobile 390×780, WCAG tags `wcag2a·2aa·21a·21aa·22aa`,
  ALL impact levels incl. minor/moderate) across **all 35 pages = 0 violations, 0 scan-errors** (`.tmp/arcU_full_impact.json`).
  Plus the FB2 serious-floor persona board re-ran **140/140** (35pg × 4 personas, fix=0 err=0, no cold-start
  transients). So the AXE-DETECTABLE WCAG 2.2 AA denominator is empty arc-wide — the U2/U3-contrast/U4/U7/U8
  rows hold measured. (Reconciliation: `ufai_battery.js` already runs the same full tag set, so this scanner
  is a confirming second oracle, not a new denominator — recall-the-move.) The genuine remaining Arc-U residual
  is the NON-axe criteria only: U6 use-of-color, U3 400% reflow, and the signed-in app-flow keyboard-trap walk.
- **✅ U1 focus-trap/restore — the one un-gated interactive residual — VERIFIED CLEAN on the representative
  app-modal (2026-07-11).** New reliable headless instrument `tools/arc_u_focus_trap_probe.mjs` (reuses FB2's
  programmatic sign-in, NOT the thrash-prone MCP browser) opened the marketplace Post sheet (`#sheet-post`,
  the AI-assist affordance's home), Tab-walked it 40× and asserted: **focus-escapes=0** (whModalA11y's trap
  contains focus — no leak to the page behind), **Escape closes**, and **focus returns to the opener `#fab-post`**
  (WCAG 2.1.2 No Keyboard Trap + 2.4.3 Focus Order, PASS). All 9 marketplace sheets are wired identically via
  the `wireSheetA11y()` → `whModalA11y` pass, so this is representative. **Evidence-discipline catch:** a first
  run FAILed focus-return — a PROBE ARTIFACT, because a programmatic `.click()` does NOT move focus, so
  whModalA11y captured no valid restore target; focusing the opener first (as a real keyboard/mouse user does)
  → PASS. A focus-restore probe MUST focus the opener before activating it.
- **U0 (study):** ✅ denominator mined (66 tap-fails / 31 pages, clustered to 2 shared + 6 page-local). This doc drafted.
- **U5 (keystone):** ✅ **DONE + VERIFIED.** 9 fixes (2 shared components + components.css `.btn-primary` floor + 5 page-local incl. the hidden-modal inline case). Full sweep: **U 202 → 234/234 = 100%**, `tap<44` = 0 on every page.
- **Whole-gate greened (own-the-gate, not just the U-lens):** clearing the U-lens exposed 3 non-U residuals on the shared frontend_ufai gate; all resolved honestly, not masked:
  - `status.html` A2+U6 (`cards=0`): rendered **placeholder health cards** synchronously (was blank-until-async-pings) → real UX win + card primitive present at first paint. A-lens → **205/205 = 100%**.
  - `index.html` F4 (root-absolute catalog-mirror links 404 on the local `/workhive/` mount, but are the **intentional prod convention** per `render_public_surface.py:104`): fixed the **battery** with a **dual-mount check** — a link is broken only if it resolves at NEITHER the literal path NOR the `/workhive/` mount (measures prod-truth; benefits every page).
  - `engineering-design.html` F6 (`hasError=false`): its 15 error handlers live in external `engineering-design.js`; the sweep scanned inline HTML only → **taught the source-scan to include the co-located sibling `.js`**. F-lens → **195/195 = 100%**.
- **NEXT:** full sweep `--update-baseline` to lock the restored all-lens 100% at the 35-page denominator → then the genuinely greenfield Arc-U residual: (1) MCP keyboard-trap walk on 3 keystone flows → (2) U6 use-of-color probe → (3) U3 reflow spot-check → register the Arc U gate. Then Stream 4 (Arc T Observability).
- **Coverage finding (2026-07-01):** `ufai_battery.js` already runs axe with the FULL WCAG 2.2 AA tag set (`wcag2a·2aa·21a·21aa·22aa`) + its own `click:not-keyboard-operable` static check. So **U1/U2/U3-contrast/U4/U7/U8 are already asserted** by the existing sweep on every page — Arc U is a *refinement*, not a greenfield stream (confirms [[project_next_arcs_program_roadmap]] R0 scoping). The genuinely net-new, un-instrumented residual is thin:
  1. **Live keyboard-TRAP detection** — axe is static; a focus trap only shows in an interactive Tab walk. Prove via a Playwright MCP keyboard-walk on the highest-interaction flows (logbook entry, marketplace listing, hive approve).
  2. **U6 use-of-color** — status conveyed by color alone (risk badges, validation, charts); axe only catches `link-in-text-block`. Needs a targeted probe/visual pass.
  3. **U3 400% reflow** — not automated; spot-check the densest pages at 400% zoom.
- **U1 keyboard operability — IN PROGRESS (2026-07-01):**
  - ✅ **Live keyboard audit on the landing** (Playwright MCP): no positive-tabindex, focus-visible present, 174 focusable; stage-card popups made keyboard-operable at runtime (`role=button`+`tabindex=0`+Enter/Space, index.html:3483) and closeable via Esc + labeled button → no trap.
  - ✅ **Skip-link (WCAG 2.4.1 Bypass Blocks, Level A) — BUILT + live-verified.** Injected as the first focusable on EVERY page via `wayfinding.js injectSkipLink()` (runs in `init()` before the home-early-return, so it covers the landing too); visually hidden until focused, then moves real focus into `<main>` (id `wh-main-content`, tabindex=-1). Verified live on index.html: Tab→focuses+reveals→activate→focus lands in main. Covers the 27 feature pages + landing (all load wayfinding.js).
  - ⏭ **Follow-up:** learn/ articles don't load wayfinding.js (SEO content layer, separate arc) → skip-link not there yet; app-flow keyboard-TRAP walk (logbook/marketplace modals) needs MCP sign-in.
- **U3 400% reflow (1.4.10) — ✅ SPOT-CHECK CLEAN (2026-07-13, Playwright @320px CSS width = 400% zoom equiv):** walked the densest pages (analytics, engineering-design, inventory) at 320px. **0 content-overflow offenders** on all three; total horizontal overflow 6-28px, and every offender is a shared DECORATIVE (`aurora-blob`) / OFF-CANVAS-hidden (`wh-fb-panel` feedback slide-out, translated to right:625 when closed) / legitimate `overflow-x:auto` scroller element — none is content. Content reflows to a single column with no horizontal scroll or clipping. Method: enumerate every element wider than the viewport whose right edge exceeds it, excluding fixed/absolute overlays + own-scrollers + the shared `wh-*`/`aurora` injector classes. Reusable as a probe if U3 is later gated.
- **U6 use-of-color (1.4.1) — ✅ SPOT-CHECK CLEAN on the app pages (2026-07-13, Playwright @320px):** audited the two highest-value status carriers — inventory STOCK levels + asset-hub RISK/criticality badges. Every meaningful status conveys by TEXT (+ color as reinforcement), never color alone: `crit-pill crit-{critical,high,medium,low}` render the literal words "critical/high/medium/low", `risk-chip`="medium risk 55%", stock = "Out of stock 0 / Low stock 3 / CLEAR". The ONLY color-only element on either page is the shared supplementary `wh-conn-dot` connectivity indicator — the SAME "1 decorative dot" the 2026-07-01 landing audit already accepted (it is supplementary, and tapping it opens `wh-conn-popover` with full text "Status: Online · Network: 4G · Pending writes: 0", and the `wh-conn-chip` carries `aria-label="Connectivity status"`). So no status-critical content relies on color alone. *(Optional future polish: add a tiny glyph/text to `wh-conn-dot` so the collapsed-view connectivity state isn't color-only pre-tap — LOW, supplementary, one shared component.)*
- **Keyboard-trap / reachability spot-check (2026-07-13, @390px):** asset-hub asset-detail is an INLINE panel (not a modal) → no keyboard trap (nothing to be trapped in); minor focus-on-open enhancement possible but not a 2.1.2 issue. **★ Investigated + DISMISSED a false alarm (an [[feedback_platform_intentional_blank_states]] instance):** the companion FAB `#wh-ai-trigger` measures 22×22px + is occluded by `#wh-hub-fab` + `elementFromPoint`≠companion in the DORMANT state — which looks like a broken/untappable sub-44 FAB. Reading companion-launcher.js (~204-220) showed it's BY DESIGN: `#wh-ai-widget` is `opacity:0; scale(0.4)` **"Hidden by default — revealed when nav-hub opens (`body.wh-hub-open`)"**, and `body.wh-hub-open #wh-ai-widget { opacity:1; scale(1) }`. VERIFIED live: opening the hub → companion widget `opacity:1`, **60×60px, reachable-by-tap** (topEl = `wh-ai-trigger-avatar`). So the companion is a member of the nav-hub's revealed set (hub→companion+feedback+conn all ≥44px), reconciling the companion-arc A-axis "companion FABs all ≥44px" (it measured the revealed state). NOT a bug — careful source-read prevented a UX-breaking "fix." **Lesson: measure a hidden-until-revealed FAB in its REVEALED state; a dormant opacity:0/scaled FAB reads as sub-44+occluded but is intentional.**
- **Keyboard-escape on the KEYSTONE shared components (on every page) — ✅ VERIFIED trap-free (2026-07-13, signed-in Pablo, @390px):** the nav-hub dialog (`#wh-hub`, opened via `#wh-hub-fab`) closes on **Esc** (`body.wh-hub-open`→false) — no trap; the companion panel (`role="dialog"`) was already A-axis-verified (focus-trap + Esc-close + labeled) in the companion arc. These two shared widgets are the highest-reuse keyboard surfaces (every page), so trap-free there covers the bulk of the risk.
- **★ KEYBOARD-TRAP WALK FOUND + FIXED A PLATFORM-WIDE A11Y BUG (2026-07-13, signed-in Pablo):** walking logbook's Register-Asset modal (`#asset-modal`, `role=dialog`) live, ESC did NOT close it AND focus did NOT enter it on open — even though the shared `whModalA11y` retrofit (Grounded Sweep C7: adds Tab-focus-trap + focus-restore + ESC-close to 7 hand-rolled logbook modals) was defined + called on it. **Root:** `whModalA11y.isOpen()` (utils.js:1303) short-circuited to `false` on the `.hidden` class BEFORE the computed-display check — but the modal opens via an inline `style.display:flex` that VISUALLY overrides its retained `.hidden` class. So the MutationObserver saw "still hidden" → never armed the ESC/focus-trap → **the retrofit silently no-op'd on every modal using the hidden-class + inline-display pattern** (the 7 logbook modals + any other page with it). **Fix:** gate the class check on the computed display — `if (classList.contains('hidden') && cs.display === 'none') return false` — so an inline-override is correctly seen as open (class-only-hidden modals still read closed via the same computed check → no regression). **VERIFIED E2E:** reopen → focus enters modal (`asset-modal-close`) ✓ · ESC closes it ✓ · focus restores to the opener ✓. Gates green: `validate_modal_a11y` (debt 0≤0) + `validate_accessibility` (5 PASS/0 FAIL). This is exactly the kind of real bug a live keyboard walk catches that the static axe sweep (which reads role/name/order, not the runtime ESC/focus-arm) cannot.
- **NEXT (this arc, ordered):** the thin remaining tail is the deeper per-page app-modal walk on OTHER pages (marketplace listing, hive-approve) — the fix above already repaired the whole hidden-class+inline-display class platform-wide; the Arc U gate is registered; axe covers static a11y. Then Stream 4 (Arc T Observability). *(2026-07-13 all clean/fixed: U3 400%-reflow ✅ · U6 use-of-color ✅ · companion-reachability ✅-intentional · nav-hub+companion keyboard-escape ✅ · **whModalA11y isOpen bug FIXED ✅**.)*
- **Cross-cutting:** stay LOCAL ([[feedback_stay_local_dont_suggest_prod_push]]); commit/deploy = Ian's standing gate, never a stop.
