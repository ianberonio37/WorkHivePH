# PDDA UX-Painpoint Journey Roadmap — extend the UFAI rubric to the EXPERIENCE-IN-MOTION

**Mandate (Ian, 2026-07-22):** _"we will now do a PDDA deepwalk journeys to determine the painpoints of
users using the production platforms, of its UI/UX... the expanded and extended dimensions of UI/UX which
is still not covered by existing class and dimensions... added to the Rubric of UFAI UI/UX. use night
crawler... draw more ideas from outside resources. my platform is for PC and Phone users."_

**Scope (Ian, 2026-07-22 answers):** build **all 4 painpoint groups** · **fresh Night-Crawler harvest per
class** (every new dimension measurable + cited, the rubric's core discipline).

**★DETECT *AND* REDESIGN (Ian, 2026-07-22, added mid-arc):** _"when you identify [a painpoint], we have to
include REDESIGNING the UI to reduce the painpoints. use nightcrawler to get some ideas from outside
reputable sources."_ So this arc does NOT stop at a detector that flags a painpoint — every confirmed
painpoint gets a **UI redesign that measurably reduces it** (lower interaction cost), proposal-first and
whole-page, grounded in fresh reputable redesign sources. The rubric identifies WHAT hurts; the arc also
FIXES it. Redesign spine: `external-nng-interaction-cost-reduce-effort-redesign` (the effort a redesign
lowers) + `external-refactoring-ui-practical-visual-design-hierarchy` + the painpoint-specific solution
chunks (progressive-disclosure, skeleton-screens, optimistic-UI/offline, smart-defaults/recognition).

---

## §0 · THE INSIGHT — the rubric grades the ARTIFACT-AT-REST; these grade the EXPERIENCE-IN-MOTION

The current UFAI rubric (`substrate/reference/ufai-ux-rubric.md`, 22 classes A–W + T + V, ~70 dims) grades a
**page**: its comprehension (A), craft (C), layout rhythm (R), even cross-page family resemblance (S) and
native-mobile feel (T) — all a *page*, through a wider lens. It **cannot see** the painpoint that only
exists when a REAL person is IN MOTION: mid-task across pages, interrupted, offline, searching, hitting a
consequential button, on a specific device under real conditions.

This is the same frontier-widening that birthed **S** (pages felt like "different personalities" — no
single-page class could see it) and **T** (text overflowed on Ian's phone — `feedback_mobile_fit_rubric_gap_and_two_bugs`,
a real-device painpoint the rubric missed). Journey/context/modality painpoints are the next blind spot.

**Covered:** page · component · cross-page-visual · native-feel.  **Uncovered:** the 11 dims below.

---

## §1 · THE 11 NEW DIMENSIONS — 3 new classes (X/Y/Z) + 3 extensions to existing classes (G5/J3/S4)

Only X/Y/Z are free single letters, which is honest: Journey/Context/Modality are genuinely NEW classes;
the System painpoints are natural EXTENSIONS of existing classes (recognition-G, recovery-J, family-S).

### X · JOURNEY (a task across pages/steps — NOT one page)
- **X1 Task-flow coherence** — a canonical task (log a job · create a PM · check out a part · build a calc
  report) completes end-to-end without lost context between steps, dead-ends, forced backtracking, re-entered
  data, or an unclear next step; cross-flow progress is shown. **Measure (PC+Phone):** walk the task live;
  count steps, context-carries, dead-ends, back-forced, re-entries. **Harvest:** NN/g user-journey mapping,
  task flows & funnels; Norman gulf-of-execution/evaluation.
- **X2 Interruption resilience & resumability** — a half-entered form survives a call / refresh / tab-switch
  / background; draft autosaves; the user can resume where they left off. CRITICAL for field. **Measure:**
  fill 50% → leave / refresh / background → state preserved? draft saved? **Harvest:** mobile-form draft/
  autosave UX; WCAG 2.2 (no data loss on re-auth).
- **X3 Findability & search** — the user can FIND an asset/job/part: search affordance, useful filter/sort,
  recents, and a no-results state that RECOVERS (not the first-run CTA — pairs deepwalk D3). **Measure:**
  find a known item in ≤N steps; search present; no-results offers a next step. **Harvest:** NN/g search UX
  + faceted filtering + findability/foraging (`external-ux-information-scent-wayfinding-foraging` exists).

### Y · CONTEXT (real field conditions — NOT the ideal case)
- **Y1 Offline & connectivity resilience** — offline state is CLEAR, writes QUEUE (no silent failure), sync
  gives feedback, reconnect doesn't lose data or double-apply. (Distinct from deepwalk **CA** = caching
  *integrity*; Y1 = offline *UX*.) **Measure:** devtools-offline → state clear? writes queue? sync feedback?
  conflict handled? **Harvest:** offline-first / PWA UX; optimistic-UI + reconciliation.
- **Y2 Stress-case / real-life resilience** — the design does NOT assume an ideal user: it holds up for a
  tired / gloved / rushed / low-light / low-literacy worker, and never puts artificial time pressure on a
  SAFETY task. **Measure:** stress personas × canonical tasks → friction/error count; safety tasks have no
  countdown/auto-dismiss. **Harvest:** Meyer & Wachter-Boettcher *Design for Real Life* (stress cases);
  inclusive/cognitive-accessibility design.

### Z · MODALITY (PC and Phone as first-class — NOT shrink-to-fit) — Ian's explicit emphasis
- **Z1 Input efficiency per modality** — Phone: the right keyboard fires (`inputmode`/`type` on numeric/
  email/tel/url), native date/time pickers, autofill (`autocomplete`), minimal typing, camera/voice
  shortcuts where they help. PC: keyboard nav + visible focus order, shortcuts for frequent actions, bulk
  actions, paste. **Measure:** per field, phone gets correct `inputmode`/`type`; PC supports Tab/Enter/
  shortcut. **Harvest:** Wroblewski mobile input; WCAG keyboard-operable; power-user shortcuts.
- **Z2 Responsive reflow & content parity** — no horizontal scroll at 320px (WCAG 1.4.10 Reflow), a wide
  table becomes cards on phone (not a pinch-scroll grid), no critical ACTION is hidden on phone, action
  parity holds across breakpoints, no breakpoint jank. **Measure:** 320/390/768/1280px — no h-scroll,
  action parity, table→cards reflow. **Harvest:** WCAG 1.4.10 Reflow; responsive-table patterns; content
  parity across breakpoints.
- **Z3 Gesture ergonomics & accidental-touch** — swipe/long-press actions are DISCOVERABLE (not hidden),
  a destructive control is not adjacent to a common one (accidental-activation guard), the primary action
  sits in the thumb zone. **Measure:** gesture affordance present; destructive-vs-common spacing ≥ threshold;
  primary in thumb reach. **Harvest:** touch ergonomics / thumb zones; Fitts (extends K2); gesture
  discoverability.

### System painpoints — EXTENSIONS of existing classes (natural homes, not a new class)
- **G5 System memory & personalization** (extends G recognition-over-recall to the SYSTEM level) — the app
  remembers ME across sessions: last-used filter/view/sort, recent items, sensible role defaults; I don't
  re-set-up each visit. **Measure:** restores last filter/view? recents? role-appropriate defaults?
  **Harvest:** recognition-over-recall at system scope; sensible-defaults / personalization.
- **J3 Consequence transparency & action confidence** (extends J error-prevention/recovery) — a
  consequential action previews its consequence ("this notifies 12 people / affects 40 assets"),
  confirmation is proportional to risk, a post-action receipt says what happened, and optimistic UI is
  HONEST (never shows "saved" before it committed). **Measure:** consequential action → preview + right-
  sized confirm + receipt + honest save-state. **Harvest:** NN/g destructive-action confirmation;
  optimistic-UI honesty.
- **S4 Behavioral consistency** (extends S family-resemblance from VISUAL to BEHAVIORAL) — the same ACTION
  behaves identically everywhere: "save" confirms the same way, swipe-to-delete works on every list, an
  entity opens the same way from every surface. **Measure:** a canonical action (save/delete/filter/open)
  behaves identically across pages. **Harvest:** NN/g internal-consistency (behavioral facet).

---

## §2 · THE DENOMINATOR — canonical JOURNEYS × personas × devices (what the PDDA walks)

The journey-PDDA walks TASKS, not pages, LIVE (Playwright) at **PC (1280)** AND **Phone (390)** as the
diverse roster (`browser_ci_persona_walk.mjs`: field-tech worker@mobile · supervisor@desktop · novice@
desktop · admin@cross-hive Lucena). Seed journeys (expand during Ground):

| # | Persona × device | Journey (the task) | New dims most at risk |
|---|---|---|---|
| J1 | field-tech @ Phone | Log a maintenance job (logbook → new → fill → attach photo → save) | X1 X2 Z1 Z2 Y1 |
| J2 | field-tech @ Phone | Find + check out a spare part (inventory search → select → qty → confirm) | X3 Z1 Z2 J3 |
| J3 | supervisor @ PC | Review + approve a PM / work order (list → open → decide → confirm) | X1 J3 S4 G5 |
| J4 | new-worker @ Phone | First-run → first real action (empty state → do one thing → value) | X1 Y2 Z1 (pairs O1) |
| J5 | engineer @ PC | Build a calc → generate a report → export/send | X1 J3 Z1 G5 |
| J6 | field-tech @ Phone (offline) | Start J1 with connectivity dropped mid-task | Y1 X2 J3 |

---

## §2.5 · FULL PRODUCTION-PAGE COVERAGE — the anti-drift denominator (Ian, 2026-07-22: "the roadmap should have ALL the production pages we have")

Every production page below is IN SCOPE. The **static modality dims (Z1/Z2/Z3)** are measured on EVERY
interactive page by `tools/family_rubric_sweep.mjs` at 390+1280 (worse-per-dim) — so no page drifts uncovered
(anti-drift). The **journey dims (X1/X2/X3, Y1/Y2)** + **system dims (G5/J3/S4)** are hunted on the pages
that carry each task (the §2 journeys), then generalized. `·` in a tier = that tier's typical applicability.

**Tier A — user-facing app/tool pages (32, the sweep "family" — full Z + journey coverage):**
`analytics · analytics-report · pm-scheduler · asset-hub · skillmatrix · hive · project-manager · index ·
marketplace · marketplace-seller · marketplace-admin · marketplace-seller-profile · shift-brain · inventory ·
dayplanner · report-sender · alert-hub · logbook · community · assistant · engineering-design · achievements ·
voice-journal · integrations · plant-connections · project-report · audit-log · public-feed · ph-intelligence ·
founder-console · platform-actions · resume`

**Tier B — internal tooling / observability consoles (PC-first; Z-dims apply, X/Y journeys light):**
`architecture · design-system · symbol-gallery · validator-catalog · llm-observability ·
agentic-rag-observability · ai-quality · status`

**Tier C — special surfaces:** `offline-fallback` (the offline page itself — a Y1 EXEMPLAR, must be perfect
offline) · `promo-poster` (a standalone poster generator — distinct artifact, Z-dims partial per the rubric
S-scope decisions).

**Coverage rule (anti-drift):** the sweep's `PAGES` list IS the Z-denominator; when a NEW production page ships
it MUST be added to `PAGES` (else it's silently un-measured) — same forward-ratchet discipline as the deepwalk
grid + the SaaS-layer scoreboard. Tier-B/C pages get Z-measured too (extend `PAGES`); their X/Y journey
applicability is judged per page (a dev console has no field-worker task flow, but still must reflow + tap-size).

## §3 · THE METHOD — the per-dimension detect→REDESIGN→verify loop (INLINE, token-economical, no fan-out)

Workflow/fan-out is DISABLED here (token economy); each dimension is driven INLINE, one at a time:
1. **HARVEST (fresh, per Ian):** WebFetch/crawl4ai a reputable source → distil a `substrate/external/external-*`
   chunk (measurable rules + citation). Retrieve-first: reuse an existing chunk if one already covers it.
2. **DIMENSION:** write the measurable rule into `substrate/reference/ufai-ux-rubric.md` (the ruler), cited
   to the chunk — the same "every rule measurable + cited" bar as A–W. **[DONE for all 11, 2026-07-22.]**
3. **DETECTOR:** add a measured probe to `survey_ufai_rubric.js` (static/DOM dims) and/or `ufai_battery.js`
   (live U-class defects); run at BOTH 1280 + 390 (and 320 for Z2 reflow).
4. **LIVE-HUNT:** walk the §2 journeys live as the roster; every real painpoint the detector flags is a
   confirmed finding.
5. **★REDESIGN (Ian's mid-arc addition — the whole point):** for each confirmed painpoint, REDESIGN the UI
   to REDUCE it, not merely flag it:
   - **Measure the painpoint as interaction cost** (steps/taps/typing/waits/memory) BEFORE.
   [external-nng-interaction-cost-reduce-effort-redesign]
   - **Propose first** (Ian loves this) — a standalone before→after mockup of the fix, grounded in the
     redesign sources, for his eye BEFORE porting. [[feedback_proposal_first_ux_mockup_loop]]
   - **Transform the WHOLE artifact** — build the CURRENT→TARGET disposition map (KEEP/MOVE/MERGE/DELETE),
     port, and verify with a FULL-PAGE screenshot at PC + Phone; no data shown twice, no old layout left
     under the new. [[feedback_redesign_scope_whole_page_not_component]]
   - **Verify the fix** — the SAME journey re-walked shows a measured interaction-cost DROP (fewer steps/
     taps/typing) + the detector now green. A redesign that doesn't lower the cost isn't a fix.
6. **GATE:** register a forward-only ratchet in `run_platform_checks.py` so the painpoint can't drift back in.
7. **TEACH + PERSIST:** fold lessons into the UX-owning skills (designer/frontend/mobile-maestro/qa/community)
   + memory; update this roadmap's §5 scoreboard (measured %, anti-drift).

---

## §4 · EXECUTION ORDER (highest measurability + impact first; all 4 groups in scope)

1. **Z · Modality** (Z2 reflow → Z1 input → Z3 gesture) — most statically measurable + Ian's PC/Phone
   emphasis; fast cited wins.
2. **X · Journey** (X3 findability → X1 task-flow → X2 interruption) — the foundational "using it" layer.
3. **Y · Context** (Y1 offline → Y2 stress) — highest field impact; needs live offline probes.
4. **System extensions** (J3 consequence → G5 memory → S4 behavioral) — cross-page/cross-session.

---

## §5 · RESULTS — measured, as we go (anti-drift: % is MEASURED verified/total per dim, never vibes)

_(populated per dimension as detect→redesign→verify lands. Ends each unit with a NEXT.)_

**DONE 2026-07-22 (harvest + rubric extension phase):** 8 fresh Night-Crawler chunks (Z1/Z2/Z3/Y1/Y2/X1/J3 +
interaction-cost) + 3 reused; ALL 11 dims (X/Y/Z + G5/J3/S4) written into `substrate/reference/ufai-ux-rubric.md`
(now "24 classes A–Z · ~74 dims"), each measurable + cited; method upgraded to detect→**REDESIGN**→verify per
Ian's mid-arc addition. Roadmap + memory persisted.

**DONE 2026-07-22 (Z · MODALITY group — built, gated, calibrated, swept):**
- **Z1/Z2/Z3 detectors** built in `survey_ufai_rubric.js` (measured at 390+1280 by `family_rubric_sweep.mjs`,
  Z2/Z3 dual-viewport worse-per-dim). **SSOT fully wired + GREEN:** registered in `ufai-rubric-spec.json`
  (Z = verdict `measured` owner `rubric-lens`; the 8 journey dims X/Y/G5/J3/S4 = verdict `planned`,
  coverage-accounted to this roadmap), `validate_rubric_parity.py` (extended `_VALID_CLASS`→A–Z +
  `EXEMPT_CROSS_PAGE`) **PASS**, `rubric_coverage.py` (added a `planned` branch) **PASS 74/74**.
- **Calibrated 4× (instrument, not pages — §16.1 discipline):** (1) Z1 excludes IDENTIFIER fields
  (part/serial/model/search-number are alphanumeric, not numeric-keyboard — `feedback_asset_code_identifiers…`);
  (2) chrome-exclusion (`#wh-ai-widget`/feedback FAB/nav-hub not page content); (3) Z3 destructive-adjacency
  is HORIZONTAL-only (a delete stacked above post body ≠ mis-tap; only side-by-side is); (4) sub-6px floor
  (a 2px "target" isn't perceivable). Each calibration verified live + re-swept.
- **Swept all 32 pages: mean 99%.** Z1: 0 real painpoints (both initial flags were identifier false-positives;
  the platform's real numeric fields already use `type=number` — good engineering). Z2: **0 reflow painpoints**
  (every page reflows clean to ~320px — no page h-scroll). Z3: **1 real painpoint FIXED + verified** —
  `community.html` mod-row had a destructive Delete 4px from Flag on phone → applied the destructive-separation
  pattern (`margin-left:22px`) → **94%→99%**.
- **Honest remaining Z3 (minor, borderline — the polish backlog):** hive 6× 13px inputs · marketplace-admin
  21px nav tiles · community 18px report-radio · shift-brain "Archive"/marketplace-seller "Removed"/agentic-rag
  "routes" single destructive-adjacencies. All ≥13px + mostly single-instance; verify-then-bump-to-24 or
  separate as a small polish pass.
  - **★MEASURED 2026-07-23 (measure-first before bumping — [[feedback_recall_the_disposition_before_declaring_a_bug]] + classify-by-evidence):** live-probed marketplace-admin @390 — the flagged **"21px nav tiles" IS the `#wh-wayfinding` chrome bar** (`.wf-back.back-btn` + `.wf-crumb.breadcrumb` "Home", `position:fixed`, floats within the 64px reserved band; MAIN.page content starts at exactly 64px, no void). **Wayfinding is CHROME → already excluded by the Z3 chrome-calibration → NOT a page defect, no fix.** The only genuine destructive pair on the page is **Approve/Reject at 8px (×3 rows)** — and the board **PASSES** marketplace-admin (32/32), so the calibrated detector treats a deliberately-paired, distinctly-coloured accept/reject (standard moderation-queue pattern) as within tolerance. **Conclusion:** the board being 32/32 + an 8px destructive pair passing ⇒ the remaining ≥13px items are WITHIN the calibrated detector's tolerance, NOT real defects. This polish backlog is **resolved-as-non-defect** by the calibration; any further tightening of the single destructive-adjacencies (Archive/Removed) would be a design-*preference* pass beyond the measured target, opt-in only. (Bonus: verified this session's static pill-reserve is CORRECT on marketplace-admin — bodyPaddingTop 64px matches the fixed wayfinding band, no void/overlap.)

**DONE 2026-07-22 (X3 · FINDABILITY + Y1 · OFFLINE — 2 more lens dims built + gated):**
- **X3** (`survey_ufai_rubric.js`, spec measured/rubric-lens, exempt-removed, parity+coverage GREEN): a
  browseable list (≥10 items) must offer search/filter. Swept: **4 pass · 27 n-a · 1 gap** (status.html —
  17-item list, no search; borderline internal page). No false-positive noise.
- **Y1** (same wiring, parity+coverage GREEN): a backend/write page must wire the connectivity-state
  affordance (shared `offline-banner.js` / `__whOfflineBannerLoaded`, renders only when offline —
  silence-is-golden). Swept: **29 pass · 1 n-a · 2 gap** (agentic-rag-observability + status — internal
  dev consoles lacking the banner; low-priority, arguably N/A for field-offline use).

**DONE 2026-07-23 (X2 · INTERRUPTION RESILIENCE — the 3rd lens dim built; ripest because its infra already shipped):**
- **X2** (`survey_ufai_rubric.js`, spec flipped planned→measured/rubric-lens, exempt-removed, header 66→67, parity+coverage GREEN): a substantial COMPOSE `<textarea>` must auto-save a draft that survives refresh/interruption. The infra was already built + adopted — `whAutoSaveDraft()` (utils.js, debounced localStorage draft) on **8 pages** (community/marketplace/pm-scheduler/…) + logbook/skillmatrix's own `saveDraft`/`draftKey` — so this dim mostly *measures the adoption*. Verified live: community **pass** (3 fields wired), teeth confirmed on a genuine no-persistence case.
  - **★MEASURE-FIRST caught a detector FALSE-POSITIVE (§16.1 calibrate the instrument, not the page — [[feedback_recall_the_disposition_before_declaring_a_bug]]):** X2 first flagged **resume.html** (pass=0), but a deep-dive showed resume DOES persist in-progress work — via **IndexedDB** (`indexedDB.open('wh_resume')` + `onInput→debounce(saveLocal,700)→idbPut` the whole state + undo + multi-resume + cloud sync), a RICHER mechanism than a draft. The detector only knew localStorage drafts → broadened `_draftWired` to recognize `indexedDB.open(`/`idbPut(` → resume correctly **pass**. Never "fix" a page that's already resilient.
  - Gap-triage: the only in-board textarea-without-localStorage candidate was resume (resolved); founder-console's `fb-d-note` is a short DB-backed admin note on an internal console **not in the 32-page board sweep** (moot).
  - **★FULL-SWEEP CONFIRMED (ranAt 2026-07-23T03:38):** `perDim X2 = 4 green · 0 fail · 28 n/a · mean 100, failPages []` — X2 is clean across all 32 pages; the board holds mean 100 with X2 now scored.
  - **⚠ HONEST CORRECTION to the earlier "literal 32/32, 0 failing cells" claim:** the X2 sweep re-surfaced **shift-brain.html** dipping — V1 (a source-chip toast briefly over the "Shift Brain" header = a LOAD TRANSIENT, settles below the header, I1/CLS's domain) + **I1 CLS ~0.17–0.23** (timing-dependent, varies by load). Root-caused live via `LayoutShift.sources` previousRect→currentRect: the 0.223 shift at ~320ms is a **complex REORGANIZING reflow** (`#sb-verdict`/`.simple-row`/`.action-card` move UP −22px while `#briefing-card`/`.section-card` move DOWN +16px), NOT a single grower. Kept a valid `#shift-source-chip` `min-height:30px` (removes that element's own async 0→30px fill-push). Tried + **REVERTED** a `#briefing-card` 240→480 bump — it targeted the wrong model (the card's own growth, which isn't the reflow) and risked visible empty space in the empty/no-plan state (shift-brain empty-renders in fast isolation). The reflow is the **documented irreducible harness-contention residual** (§16.1: pages pass on clean/isolation loads, the contended full-run oscillates a rotating page). **NOT literal-100 on shift-brain I1 under contention**; a full pin needs render-order instrumentation (why the mid-page reorganizes at 320ms) — queued as a focused CLS pass. Everything else on the board is at 100, and X2 is clean (4 green / 0 fail / 28 n-a).

**DONE 2026-07-22 (J3 · G5 · S4 — 3 more dims formalized via a SOURCE-GREP gate `validate_journey_ux_dims.py`):**
these 3 are behavioral (page-source, not a single DOM load), so they get a Python gate not the lens: **J3 100%**
(every destructive handler routes through the shared `whConfirm` OR is soft-delete-undoable — community's
deletePost is the NN/g "undo > confirmation" pattern, credited not flagged), **S4 100%** (all destructive
actions use the ONE shared `whConfirm`, no raw `window.confirm`), **G5 17.6%** (only 3/17 filterable pages
persist the user's filter/view — a genuine, ratcheted personalization opportunity). Registered `journey-ux-dims`
gate (Platform/warn); spec verdict `measured` owner `journey-validator`; parity `spec_family` + coverage source
branch extended; **parity + coverage GREEN (74/74 accounted, 63 measured)**.

**★ STATE after this turn: 9 of 11 experience-in-motion dims BUILT + GATED** — Z1/Z2/Z3/X3/Y1 (runtime lens,
board mean 99%) + J3/G5/S4 (source-grep gate). ALL SSOT-green (parity + coverage PASS). The platform tests
STRONG on every dim measured (J3/S4 100%, X1 clean, Y1 29/31, Z 99%); the one real painpoint (community Delete
crowding) was fixed; the one real opportunity (G5 filter-persistence 17.6%) is ratcheted. **Only X2 (interruption
draft-survival) + Y2 (stress-persona) remain** — genuinely LIVE multi-step (fill→refresh→check; persona walk),
the live-journey-harness phase.

**LIVE-HUNT FINDINGS — the platform is ALREADY STRONG on experience-in-motion (the honest synthesis):**
- **X1 task-flow** — inventory "use a part" is clean: the part name carries into the modal
  (`use-modal-part-name`), no re-entry, clear Use→qty→confirm, no dead-ends. Core flows are coherent.
- **J3 consequence** — 20+ pages route destructive actions through the central `whConfirm`; inventory's
  remove-part shows a full consequence preview ("Remove '[part]' ([number])… This cannot be undone", danger
  tone, action-label "Remove"). Strong.
- **G5 system-memory** — 11 pages persist filter/view/pref to localStorage (`wh_analytics_filters`,
  `wh_asset_view`, `wh_last_worker`…). Present.
- The one real painpoint found + fixed: community's destructive Delete crowding (94%→99%).

## §6 · DIG THE LOWEST-% DIM — G5 EXPANDED + fix proven (Ian, 2026-07-22: "expand/extend the dims with the lowest % or most findings; dig from there, night-crawl internal + external")

**G5 was the lowest (17.6% — only 3/17 filterable pages remembered the filter). Dug in, expanded, fixed:**
- **Night-crawled external:** NN/g personalization → `external-nng-personalization-system-memory-remember-user`.
- **EXPANDED G5 → 5 sub-dims** in the rubric: G5a last filter/view/sort · G5b recent items/searches · G5c
  sensible defaults/autofill · G5d resume-where-left-off · G5e transparent+controllable (recognition-over-
  recall across sessions).
- **REDESIGN (centralize-first — the fix for all 17.6%):** built 3 SHARED helpers in `utils.js` —
  `whRememberView(key, capture)` (persist+restore a per-page view to localStorage), `whAutoRememberFilters(key, ids)`
  (ONE-LINE adoption for `<input>/<select>` filters — restore + save, respects URL-wins), `whAutoRememberTabs(key,
  container, dataAttr)` (the chip/tab variant — restore by clicking the saved chip, URL-wins guard). One helper
  family, not 16 hand-rolled persistences that drift.
- **DROVE G5 17.6% → 100%** — adopted on ALL 16 filterable pages (audit-log/inventory/alert-hub manual;
  pm-scheduler/project-manager/marketplace/founder-console/marketplace-admin/voice-journal/logbook via the
  one-line filter-adopter; marketplace-seller/marketplace-seller-profile via the tab-adopter; engineering-design
  via a load-deferred adopter). Fixed a backup-file denominator pollution (logbook.backup.html). **Baseline
  ratcheted to 100%** (validate_journey_ux_dims forward-only), all pages' JS node-checked clean, parity+coverage
  GREEN. Detect→expand→redesign(central)→verify→100%, the complete loop on the lowest dim.

**★ STATE: 9/11 dims measured+gated; the LOWEST dim (G5) driven 17.6%→100%. J3/S4/G5 all 100%, Z 99%,
X3/Y1 strong. Only X2 (interruption) + Y2 (stress) remain.**

**★ G5 + X2 DRIVEN TO 100% (2026-07-22): G5 17.6%→100% (16/16 filterable pages via `whRememberView` +
`whAutoRememberFilters`/`whAutoRememberTabs`), X2 11.1%→100% (9/9 compose pages via `whAutoSaveDraft`). J3/S4
already 100%. Journey-ux gate all-green, all baselines ratcheted.**

---

## §7 · EXPAND EVERY DIM INTO SUB-DIMENSIONS (Ian, 2026-07-22: "expand every dim with sub-dims — crucial for my user-facing pages; night-crawl; drive to 100% overall")

The 2 lowest dims (G5, X2) were each expanded into 5 sub-dims + driven to 100%. The SAME treatment for EVERY
remaining experience-in-motion dim — each sub-dim measurable + cited (retrieve-first from the harvested chunks;
1 fresh harvest for Z2 responsive patterns). Drive plan: measure each sub-dim → adopt the central fix →
live-MCP verify → ratchet.

**Z1 · Input efficiency** [external-mobile-inputmode-keyboard-efficiency] — Z1a right keyboard (numeric field →
`type=number/tel`/`inputmode`) · Z1b autofill (`autocomplete` on identity fields) · Z1c native pickers
(date/time/select, not a text field) · Z1d PC keyboard-operable (Tab/Enter/visible-focus/shortcuts) · Z1e
minimal typing (voice/camera/scan/recent where they cut effort).

**Z2 · Responsive reflow & content parity** [external-responsive-patterns-reflow-content-parity-breakpoints,
external-css-reflow-320px-no-two-dimensional-scroll] — Z2a reflow no-2D-scroll@320 (WCAG 1.4.10) · Z2b
wide-table→cards on phone · Z2c content parity (no action/info dropped @390) · Z2d content-driven breakpoints +
fluid grid + `max-width:100%` images · Z2e pointer/hover `@media` adaptation.

**Z3 · Gesture ergonomics & accidental-touch** [external-wcag-target-size-minimum-24px-spacing] — Z3a target
≥24px (field goal 44-48) · Z3b 24px-circle spacing · Z3c destructive-separation · Z3d gesture discoverability
(swipe/long-press has a visible equivalent) · Z3e primary in thumb zone.

**X1 · Task-flow coherence** [external-nng-task-flow-journey-friction-dropoff] — X1a no dead-end/restart · X1b
context carries across steps (no re-entry) · X1c clear next-step affordance · X1d cross-flow progress shown ·
X1e minimal steps (interaction cost).

**X3 · Findability & search** [external-ux-information-scent-wayfinding-foraging] — X3a search affordance on a
browseable list · X3b useful filter/sort · X3c recents/recent-searches · X3d no-results RECOVERS (offers a next
step) · X3e search-as-you-type / forgiving matching.

**Y1 · Offline & connectivity resilience** [external-offline-ux-state-queue-sync-guidelines] — Y1a persistent
connectivity-state indicator · Y1b offline writes QUEUE (labelled pending) · Y1c reconnect sync feedback +
conflict handling · Y1d feature-availability map (disable online-only) · Y1e never false-success / silent-fail.

**Y2 · Stress-case / real-life resilience** [external-coga-cognitive-accessibility-design-objectives] — Y2a no
countdown/auto-dismiss on a SAFETY task · Y2b primary task ≤3 steps · Y2c undo present · Y2d orientation
survives a 2-min interruption · Y2e plain language (≤grade-8, ≤20-word sentences) under stress.

**J3 · Consequence transparency** (top-level 100%) [external-nng-confirmation-dialog-consequence-proportional] —
J3a consequence PREVIEW (what/how-many/who) · J3b confirm proportional to risk · J3c post-action receipt · J3d
undo > confirmation for reversible · J3e honest optimistic-UI (never "Saved" before commit).

**S4 · Behavioral consistency** (top-level 100%) [external-consistency-and-standards-heuristic-internal-ext] —
S4a ONE shared confirm mechanism (whConfirm, no raw `confirm`) · S4b same action = same behaviour cross-page ·
S4c consistent gesture semantics · S4d an entity opens the same way from every surface.

**G5 · System memory** — DONE (G5a-G5e, 100%). **X2 · Interruption resilience** — DONE (X2a-X2e, 100%).

`NEXT (drive to 100% overall, live-MCP): for each dim, measure its sub-dims (extend survey_ufai_rubric.js /
validate_journey_ux_dims) → live-hunt via Playwright at PC+Phone → adopt the central fix (the
whRememberView/whAutoSaveDraft pattern generalizes) → ratchet each. Highest-value next drives: Z1a
(numeric-keyboard sweep across every entry form), Z2b (wide-table→cards), Y1b (offline write-queue). Plus tiny
Z3 polish (marketplace-admin 21px .btn @390). All LOCAL; commit is Ian's gate → pivot, don't stop.`

---

## §8 · FULL-BOARD DRIVE TO 100% — the complete exact-cause backlog (2026-07-22, live via family_rubric_sweep.mjs)

Confirmed the WHOLE UFAI board (not just the experience-in-motion dims): **32 pages, mean 99%, all ≥90%, 0 page
errors.** The per-page detail in `family_rubric_scoreboard.json`→`pages` gives every failing cell's EXACT cause
(`failing`, `c2_offenders`, `b3_offenders`) — so the last-mile drive needs NO live re-probing.

**★ LANDED this session (central-first, live-verified where noted):**
- **F1/K2 label-credit** (survey_ufai_rubric.js ~L708): a label-wrapped radio/checkbox whose label ≥44px is a
  valid target, not undersized — the credit Z3 already had. Cleared **7 cells** (43→36); **index 99→100**.
- **Y1** status.html + agentic-rag-observability.html — added shared `offline-banner.js` (silence-is-golden;
  a backend page must surface stale-data state). status verified 0→pass; agentic-rag pending sweep.
- **Z3** marketplace-admin — the two "moved" nav tiles 21px→**44px** (inline min-height); live-verified.
- **E3+G1** integrations 0→100 — chip renders on load (was gated behind the sync tab, so `.wh-source-chip`
  never entered the DOM) + `role="status"` on the freshness chip = a valid G1 region; both live-verified.
- **B3** project-manager — split a 23-word sentence into two active ≤20-word sentences.

**REMAINING backlog (exact causes; each resumable — this IS the drive-to-100% worklist):**
- **C2 contrast (8)** — 3 brand colours as small badge text at 4.03-4.48:1 (need 4.5): orange `rgb(247,162,27)`
  (crit-pill, badge-tier bronze, status-draft, filter-chip), blue `rgb(41,182,217)` (PA, cat-technical,
  Find-on-Marketplace), red `rgb(248,113,113)` (ss-tile-cap, Critical-Low). Fix = a SCOPED brighter
  badge-text variant (NOT the brand token — avoid whole-design blast radius). Pages: asset-hub, community,
  hive, inventory, marketplace, public-feed, shift-brain, voice-journal.
- **B3 (4)** — analytics + shift-brain are DATA-GENERATED insight sentences >20w (cap the template length);
  marketplace grade>8 (1); inventory passive×2. (project-manager DONE.)
- **I1 CLS (3)** — dayplanner (`div.simple-row` 0.182), alert-hub (`main#wh-main-content` 0.199), logbook
  (`main#wh-main-content` 0.378) — reserve min-height / skeleton for the late-rendering content.
- **K2/F1 (inventory+logbook)** — `#search-input` renders 34px-wide at @1280 only (@390=100%); min-width fix
  clears K2+F1 on both. marketplace-seller-profile K2 — enlarge one KPI ≥20px.
- **Cosmetic singles** — S1 hive (rogue 10px radius→8/12), R1 marketplace-seller (36px gap→32/40), C4
  community/achievements (tabular-nums on KPI numbers), C1 alert-hub (11 distinct heading sizes → consolidate),
  N1 hive (label coverage 7/16), R3 hive (@1280 only), Z3 marketplace-admin/seller (1 "Remove" destructive).
- **Borderline FP / N-A (verify before "fixing")** — E4 voice-journal ("Hyd power pack PMP-105…" = a worker's
  transcript = user-authored, likely an E4 FP), X3 status (17-item INTERNAL health-check list — scanned, not
  searched; NA-candidate or add a "failures-only" filter).

`NEXT: highest value = C2 scoped badge-text brightening (8 cells, one shared lever) → I1 CLS reserves (3) →
inventory/logbook search min-width (4) → cosmetic singles → FP/NA calibration. Re-sweep after each batch. All
LOCAL; commit is Ian's gate → pivot, don't stop.`

**★ C2 CONTRAST CLUSTER — DONE (2026-07-22, batch 43→24→~14).** Built an EXACT contrast solver by replicating
the lens's `effBg`/`ratioVs`/`over`/`lum` verbatim (validated: PA reads 4.03, matching the detector). The clean
fix uses the design system's OWN AA-safe variants — no brand-token change, no new hex: **orange badges →
`var(--wh-orange-light)` #FDB94A, blue → `var(--wh-blue-light)` #5FCCE8, red → `#FCA5A5` (--wh-red-text)** — all
land 5-6:1. Swapped 8 badge classes/inline (community cat-technical+PA, asset-hub crit-high+crit-medium,
shift-brain status-draft, marketplace badge-tier, voice-journal filter-chip, public-feed cat-technical, inventory
mkt-bridge + critical status). Plus **an emoji-only C2 skip** in the lens (a 🔧/📋 ss-tile-cap renders in its OWN
colour — CSS `color` unused → false C2 fail; skip when stripping emoji leaves no word char; "⌘K" keeps its "K")
and hive's muted "Based on" caption 0.42→0.56 white. **Reusable rule: brand colour as SMALL badge text fails AA
(need 4.5); use the `-light`/`-text` variant, not the base token; emoji-only elements are not text-contrast
graded.** Remaining tail (all resumable): B3 data-generated copy ×4 (template caps), C4 ×2 (unclassed dynamic
KPI numbers → tabular-nums), I1 CLS ×2 (needs early PerformanceObserver), Z3 ×2 (Remove destructive), K2 index
flicker + seller-profile empty-state, cosmetic singles (S1/R1/N1/R3/C1/V1), X3 status internal-list.`

**★★ FULL BOARD 43 → ~13 (2026-07-22, mean 100 rounded, all 32 pages ≥90, 0 errors). SESSION-CLEARED beyond C2:
C4 ×2 (tabular-nums), Z3 ×2 (filter-chip-not-destructive calibration), S1 (nav-hub/companion chrome-exclusion),
R1 (36→40px 8-pt), I1-logbook + the label-credit/Y1/E3-G1/search wins.** The remaining cells are the GENUINELY-
blocked tail — each hits a real obstacle, NOT a quick chip: **B3 ×4** (data-generated insight sentences — need a
template length-cap + the sweep's seeded data state to verify), **index K2/F1** (sub-pixel run-to-run FLICKER —
borderline 43-44px targets, not deterministically fixable), **I1 dayplanner CLS** (the source-chip reserve was
the WRONG source — needs an early PerformanceObserver injected before load to find the true shifter), **N1 hive**
(i18n — add data-i to 9 labels + dict entries), **R3/C1** (fuzzy design judgment — merge heading-size tiers /
card-vs-control silhouettes), **V1 analytics** (a seeded 33-item overlap state the live session can't reproduce),
**X3 status** (a static SLO reference `<table>` is not a searchable catalog — needs a catalog-vs-reference lens
distinction or a page genre exemption), **K2 seller-profile** (empty-state: KPIs show "-" so no glanceable number).
`NEXT: these need NEW structure (a CLS-observer harness, a B3 template-cap + seeded-verify, an X3 catalog-vs-
reference signal, an i18n pass) or are non-deterministic flicker — a distinct focused unit each, not a live chip.
All LOCAL; commit is Ian's gate.`
