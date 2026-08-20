// dialog_targets.mjs — the ONE source of truth for how each V2/V3 dialog in the page bank is opened.
//
// Extracted 2026-08-13 so the modal-exit prover and the dialog-layout prover cannot drift apart. Every
// entry's open path was READ FROM SOURCE, never matched by label: a generic opener regex once matched
// "Load more posts" instead of a composer, and a mechanical sweep resolved only 4 of 15. Each carries the
// `ref` that establishes it, so a target that stops working names the line to re-read.
//
// Fields:
//   openBy 'click' + opener  — a real element; focus-restore is assertable against it
//   openBy 'fn'    + fn      — the page's own opener function; Escape-closes only, because focus at open
//                              time is <body> and a restore assertion would measure the probe's own state
//   pre                      — a precondition that reaches the state revealing the opener (state-gated
//                              controls, empty default views); its failure is UNGRADED, never a defect
//   signedOut                — the dialog only exists for a signed-out visitor
//   mayStartOpen             — the page raises it itself on load, so there is no open step to drive
//   unreachable              — a VERIFIED source fact that the control can never be reached (a finding)
//   notDrivable              — no read-only path in; listed so it stays in the denominator

export const TARGETS = [
  { page: 'inventory', view: 'V2', modal: 'part-modal', openBy: 'click', opener: '#btn-add-part',
    ref: 'inventory.html:1957 btn-add-part -> openAddModal() -> :1333 part-modal display=flex' },
  // A PRECONDITION, because the opener is STATE-GATED and the first run reported it as "absent or not
  // visible" — #btn-edit-asset ships with class `hidden` and is only revealed by renderDetail(), gated on
  // canEdit (pm-scheduler.html:1861-1863). Without selecting an asset there is no Edit control to click,
  // which is a fact about the page, not a defect. openDetail(assetId) is global
  // (pm-scheduler.html:1796), so the real path is reachable — and because it leaves a REAL button to
  // click, focus-restore stays assertable here rather than degrading to the function-call path.
  { page: 'pm-scheduler', view: 'V3', modal: 'pm-edit-modal', openBy: 'click', opener: '#btn-edit-asset',
    // Drive the REAL user path — click an asset card — rather than calling openDetail(assets[0].id):
    // `assets` is module-scoped, not on window, so the first version threw "no assets loaded" and would
    // have reported a page fact as an instrument failure. The card carries onclick="openDetail('<id>')"
    // at pm-scheduler.html:1758, so clicking it is both reachable and the path a person actually takes.
    pre: 'var c = document.querySelector(".asset-card"); '
       + 'if (!c) throw new Error("no .asset-card rendered — this hive has no PM assets"); c.click();',
    ref: 'pm-scheduler.html:2061 openEditPMAsset() sets #pm-edit-modal display=flex; opener '
       + '#btn-edit-asset at :643 (onclick=openEditPMAsset), revealed by renderDetail() at :1863; '
       + 'whModalA11y registered explicitly at :2909' },
  { page: 'resume', view: 'V3', modal: 'resume-manager', openBy: 'click', opener: '#btn-resumes',
    ref: 'resume.html openResumeManager() reveals #resume-manager; opener id read from source' },
  // ★CORRECTED 2026-08-18 — THIS WAS MARKED notDrivable AND IT IS DRIVABLE. The old entry said
  // "openReview() is module-scoped and not callable from the page, so there is no read-only path in", and
  // on that basis every consumer of this file skipped resume V2. It is wrong: resume.html ends its IIFE
  // with `window.WHResume = { get, set, openReview, snapshotVersion, srcChip }`, so openReview IS exposed.
  // Driven live this session with three synthetic items and a spy onConfirm — the sheet opened, unchecking
  // a row moved its confirm count 3 -> 2, an edited value carried through, and the single confirm
  // invocation received exactly the edited + still-checked items. No upload, no resume-extract call, and
  // NO write of any kind.
  // Which matters twice over: this file's own header exists because "an omitted target silently shrinks
  // the denominator", and a notDrivable claim is the softest way to omit one. It cost nine provers a view.
  // The caller supplies the items, so the fixture lives here rather than in the page — keep the shape
  // openReview expects ({ group, label, value, checked, src }) and a no-op onConfirm so nothing commits.
  { page: 'resume', view: 'V2', modal: 'review-sheet', openBy: 'fn',
    fn: "window.WHResume.openReview('Review what we found', ["
      + "{ group: 'Work Experience', label: 'Was: Maintenance Tech', value: 'Maintenance Technician, Line 3', src: 'file', checked: true },"
      + "{ group: 'Work Experience', label: 'Was: PM rollout', value: 'PM rollout', src: 'file', checked: true },"
      + "{ group: 'Skills', label: 'Was: welding', value: 'Welding', src: 'file', checked: true }"
      + "], function () {})",
    ref: 'resume.html openReview(title, items, onConfirm) adds .open to #review-sheet; exposed as '
       + 'window.WHResume.openReview at the end of the page IIFE (verified live 2026-08-18)' },
  { page: 'community', view: 'V3', modal: 'composer-overlay', openBy: 'click', opener: '#fab-post',
    ref: 'community.html openComposer() reveals #composer-overlay; opener #fab-post read from source' },
  { page: 'skillmatrix', view: 'V2', modal: 'lesson-modal', openBy: 'fn', fn: "openModal('lesson-modal')",
    ref: 'skillmatrix.html:1253 openModal(\'lesson-modal\') — shared openModal(id)/closeModal(id) helper' },
  { page: 'skillmatrix', view: 'V3', modal: 'exam-modal', openBy: 'fn', fn: "openModal('exam-modal')",
    ref: 'skillmatrix.html:1522 [\'lesson-modal\',\'exam-modal\',\'result-modal\'] registered together' },
  // THE ONE DIALOG NOT ON THE SHARED HELPER — index hand-rolls its own Escape, so this is the target that
  // actually tests the divergence rather than the convention. It must run SIGNED OUT: openSignIn() checks
  // whWorker() first and, for a signed-in caller, opens the user menu and returns without showing the
  // modal at all (index.html:2917). index does track its opener (`_signinOpener`, index.html:2918), so
  // focus-restore is a fair question here — but it is opened by a function call, so this run asserts only
  // Escape-closes.
  { page: 'index', view: 'V3', modal: 'signin-modal', openBy: 'fn', fn: 'openSignIn(null)',
    signedOut: true,
    ref: 'index.html:2914 openSignIn(e) removes .hidden from #signin-modal after an early return to '
       + 'toggleUserMenu() for signed-in callers; the ONLY dialog in the roster not registered with '
       + 'whModalA11y (per prove_modal_escape_adoption.mjs)' },
  // The level-up overlay is a CELEBRATION — it only appears the moment a worker crosses a level, which no
  // read-only probe can cause. So it is opened with a REAL achievement id taken from the page's own
  // ACHIEVEMENT_DEFS (showLevelUpModal early-returns on an unknown id, so a made-up one would silently do
  // nothing and read as "did not become visible"). The overlay is genuine; only the triggering event is
  // synthetic, and nothing is written — it renders a badge and removes .hidden.
  { page: 'achievements', view: 'V3', modal: 'levelup-overlay', openBy: 'fn',
    fn: 'showLevelUpModal(Object.keys(ACHIEVEMENT_DEFS)[0], 2, false)',
    // The arguments BECOME the content: showLevelUpModal renders newLevel into the overlay, so the "2" this
    // call passes shows up as a rendered value. The session-died prover read that 2 as a figure that had
    // outlived the session — it is the probe's own input. Flagged so that oracle abstains here; the layout
    // and a11y oracles are unaffected, because a synthetic level still lays out and labels like a real one.
    syntheticContent: true,
    ref: 'achievements.html:933 showLevelUpModal(achievementId,newLevel,isTierUp) removes .hidden from '
       + '#levelup-overlay at :942; closeLevelUpModal() at :944' },
  { page: 'pm-scheduler', view: 'V2', modal: 'completion-sheet', openBy: 'fn', fn: 'openSheet()',
    ref: 'pm-scheduler.html:2046 openSheet() adds .open to #completion-sheet; whModalA11y registered '
       + 'explicitly at :2910 with onClose: closeSheet' },
  // The opener here is RENDERED, not static — post cards carry onclick="openThread('<id>')" — so the
  // selector targets that attribute rather than an id. It is still a real clicked ELEMENT, which is why
  // focus-restore stays assertable on this target instead of degrading to the function-call path.
  { page: 'community', view: 'V2', modal: 'thread-overlay', openBy: 'click',
    opener: '[onclick*="openThread"]',
    ref: 'community.html:931 openThread(id) opens #thread-overlay; openers are rendered post cards '
       + 'carrying onclick="openThread(...)" (see the .reaction-btn rule at community.html:210)' },
  // Both openers below are real rendered elements, so focus-restore is assertable — and both open paths
  // were checked for WRITES before being driven (`generateHandover()` and logbook's `openModal(id)` each
  // contain no insert/update/upsert/delete/rpc/functions.invoke), because this prover must not touch the
  // shared test database.
  { page: 'hive', view: 'V2', modal: 'handover-sheet', openBy: 'click', opener: '.handover-btn',
    unreachable:
      'THE SHIFT HANDOVER FEATURE HAS NO REACHABLE ENTRY POINT. The only control that calls '
      + 'generateHandover() is .handover-btn at hive.html:1417, and it lives inside '
      + '#handover-panel (hive.html:1411) which ships class="hidden". Repo-wide, across every .js and '
      + '.html, "handover-panel" appears ONLY at that declaration — nothing ever removes the class — and '
      + 'generateHandover is referenced only by its definition at :5616 and that one button. Measured '
      + 'live at 390, 641 and 1280: the panel computes display:none at every width, still carries '
      + '.hidden, and the button has zero height, so this is not a breakpoint or a collapsed <details>. '
      + 'The feature itself is fully built — generateHandover() populates #handover-body, the sheet is '
      + 'registered with whModalA11y via the id array at :1565, there is a source chip '
      + '(#handover-source-chip) and a "Handover to (incoming technician)" field — so a complete, wired '
      + 'shift-handover flow is shipped with its door bricked up. NOT auto-fixed, because WHERE the entry '
      + 'point belongs (the board, a nav item, the shift card) is a design decision, and un-hiding a '
      + 'panel blind could surface something deliberately parked.',
    ref: 'hive.html:1417 .handover-btn onclick="generateHandover()" reveals #handover-sheet; registered '
       + 'via the id array at hive.html:1565; panel #handover-panel at :1411 is class="hidden"' },
  // TWO RENDER PATHS, so the selector is the ATTRIBUTE, not the class. `.entry-card` (logbook.html:3767)
  // measured count=0 even at 10s on a hive that demonstrably has entries — because the list actually on
  // screen is the second path at :5823, an inline-styled div with `onclick="openModal('<id>')"` and no
  // class at all. Selecting on the handler covers both paths and cannot drift when one is restyled.
  // PRECONDITION: switch to "My Entries". Measured on the default view, `[onclick^="openModal("]` counts
  // ZERO — and so does Team Feed — while My Entries renders 23 openers over 20 entry cards. So the
  // earlier "opener absent or not visible" was a VIEW state, not missing data and not a defect: the feed
  // this identity lands on has nothing of its own to open. Clicking the real filter button is the path a
  // person takes.
  // ★WAIT AFTER THE PRECONDITION BEFORE CLICKING THIS OPENER (2026-08-19). The opener lives in the
  // entry-card template (logbook.html:3823), so it does not exist at rest: measured 0 cards and 0
  // openers before the pre, then 20 cards and 23 openers 4.5s after it. A probe that runs the pre and
  // clicks immediately reports the opener 'absent' and the whole view silently UNGRADES - which reads
  // exactly like a stale target and nearly got recorded as one. The target is fine; it needs a settle.
  { page: 'logbook', view: 'V2', modal: 'modal', openBy: 'click',
    opener: '[onclick^="openModal("]',
    pre: 'var b = document.getElementById("btn-view-mine"); '
       + 'if (!b) throw new Error("#btn-view-mine absent — the view filter moved"); b.click();',
    ref: 'logbook.html:3767 .entry-card and :5823-5825 the inline-styled open-entries row, both '
       + 'onclick="openModal(\'<id>\')" -> :3903 removes .hidden from #modal' },
  { page: 'report-sender', view: 'V3', modal: 'sheet-overlay', openBy: 'click',
    opener: '#add-contact-btn',
    ref: 'report-sender.html:613 #add-contact-btn -> :1994 addEventListener click openAddSheet -> '
       + ':1314 openAddSheet() sets #sheet-overlay display=flex' },
  { page: 'hive', view: 'V3', modal: 'intent-capture', openBy: 'fn', fn: '_openIntentModal()',
    mayStartOpen: true,
    ref: 'hive.html:3598 _openIntentModal(preset) shows #intent-capture; registered via the id array '
       + 'at hive.html:1565. It is a FIRST-RUN prompt the page raises itself, so on a fresh profile it '
       + 'is already open when the page settles' },

  // ── TAB VIEWS (kind: 'tab') ────────────────────────────────────────────────────────────────────────
  // A V2/V3 that is a TAB, not an overlay. Same open-then-measure shape — click the tab, root the
  // measurement at its PANEL — but the exit question is different, so `kind` keeps the provers honest:
  // the modal-exit prover SKIPS these (a tab panel does not close on Escape; the way out of a tab view is
  // the page-level affordance, which is a separate measurement), while the layout and a11y provers include
  // them, because overflow, tap targets, names, focus and motion are all exactly as meaningful in a panel.
  // Without `kind` the escape prover would demand Escape close a tab and report a fabricated defect on
  // every one.
  { page: 'asset-hub', view: 'V2', modal: 'rel-panel-fmea', kind: 'tab',
    openBy: 'click', opener: '.rel-tab[data-tab="fmea"]',
    // PRECONDITION: the reliability tabs live inside #reliability-card inside #detail-view, which
    // ships display:none — asset-hub opens on the asset TREE and you must open an asset first.
    // Measured: the tab button exists but has height 0 with #detail-view display:none two levels up.
    // asset-hub.html:1524 wires every [data-node-id] element to openDetail(), so clicking one is the
    // real path in. Its absence is a hive-data state and is UNGRADED, never a defect.
    pre: 'var n = document.querySelector("[data-node-id]"); '
       + 'if (!n) throw new Error("no [data-node-id] rendered — this hive has no asset nodes"); '
       + 'n.click();'
       // TWO gates, not one. #detail-view AND #reliability-card are separately display:none, and the
       // second is a progressive-disclosure toggle: "Show Reliability Workbench (engineer view)" at
       // asset-hub.html:674, carrying aria-controls="reliability-card". Opening an asset alone leaves the
       // tabs at height 0, which the first attempt reported as "opener not visible" — true, and not a
       // defect: the workbench is deliberately collapsed for a non-engineer view.
       + 'var w = document.querySelector("[aria-controls=\\"reliability-card\\"]"); '
       + 'if (!w) throw new Error("no reliability-workbench toggle found"); '
       + 'if (w.getAttribute("aria-expanded") !== "true") w.click();',

    ref: 'asset-hub.html:685 .rel-tab[data-tab=fmea] -> :690 #rel-panel-fmea; the switcher at :3094-3097 '
       + 'maps each data-tab to its panel. This is the DEFAULT active tab, so the panel is already shown '
       + 'when the page settles; clicking it is still the real path and is idempotent.' },
  { page: 'asset-hub', view: 'V3', modal: 'rel-panel-weibull', kind: 'tab',
    openBy: 'click', opener: '.rel-tab[data-tab="weibull"]',
    pre: 'var n = document.querySelector("[data-node-id]"); '
       + 'if (!n) throw new Error("no [data-node-id] rendered — this hive has no asset nodes"); '
       + 'n.click();'
       // TWO gates, not one. #detail-view AND #reliability-card are separately display:none, and the
       // second is a progressive-disclosure toggle: "Show Reliability Workbench (engineer view)" at
       // asset-hub.html:674, carrying aria-controls="reliability-card". Opening an asset alone leaves the
       // tabs at height 0, which the first attempt reported as "opener not visible" — true, and not a
       // defect: the workbench is deliberately collapsed for a non-engineer view.
       + 'var w = document.querySelector("[aria-controls=\\"reliability-card\\"]"); '
       + 'if (!w) throw new Error("no reliability-workbench toggle found"); '
       + 'if (w.getAttribute("aria-expanded") !== "true") w.click();',

    ref: 'asset-hub.html:686 .rel-tab[data-tab=weibull] -> :704 #rel-panel-weibull (ships '
       + 'style="display:none", revealed by the switcher at :3094-3097)' },

  // dayplanner renders ALL FOUR period views into ONE shared container (#calendar-wrap, written by
  // renderWILO/renderMILO via render() at dayplanner.html:1066) rather than swapping panels — so V2 and V3
  // share a root id and differ only by which tab is active. That is exactly the distinction the rows draw,
  // and rooting at the container means each is measured on what is actually rendered for that view.
  { page: 'dayplanner', view: 'V2', modal: 'calendar-wrap', kind: 'tab',
    openBy: 'click', opener: '#tab-wilo',
    ref: 'dayplanner.html:336 #tab-wilo onclick=switchView[wilo] -> :1043 switchView -> render() -> '
       + 'renderWILO writes #calendar-wrap' },
  { page: 'dayplanner', view: 'V3', modal: 'calendar-wrap', kind: 'tab',
    openBy: 'click', opener: '#tab-milo',
    ref: 'dayplanner.html:337 #tab-milo onclick=switchView[milo] -> :1043 switchView -> render() -> '
       + 'renderMILO writes #calendar-wrap' },
  { page: 'engineering-design', view: 'V2', modal: 'tab-history', kind: 'tab',
    openBy: 'click', opener: '.page-tab[data-tab="history"]',
    ref: 'engineering-design.html:614 .page-tab[data-tab=history] onclick=switchTab[history] -> :868 '
       + '#tab-history (ships class="hidden")' },
  { page: 'engineering-design', view: 'V3', modal: 'tab-guide', kind: 'tab',
    openBy: 'click', opener: '.page-tab[data-tab="guide"]',
    ref: 'engineering-design.html:615 .page-tab[data-tab=guide] onclick=switchTab[guide] -> :884 '
       + '#tab-guide (ships class="hidden")' },

  // -- SECTION VIEWS (kind: 'section') -------------------------------------------------------------------
  // The THIRD V2/V3 shape. Several pages' V2/V3 are neither an overlay nor a tab but a SECTION that is
  // already rendered on load -- the executive-summary block, the predictive block, the verdict card. There
  // is nothing to open, so `mayStartOpen` is set and no opener is needed; the layout and a11y provers skip
  // the open step and measure the section as their root, which is exactly right. Like tabs, sections are
  // skipped by the modal-exit prover: a section has no Escape and never did, and the way out of the page is
  // the V1 back_out row.
  // WHY THIS IS NOT CHEATING THE V2/V3 DISTINCTION: the row asks about a VIEW, and for these pages the
  // anatomy defines the view as that section (see each `ref`). Measuring the section is measuring the view;
  // measuring document.body would be re-measuring V1 and banking it as V2, which is the error the whole
  // dialog harness was built to avoid.
  { page: 'analytics', view: 'V2', modal: 'an-summary', kind: 'section', mayStartOpen: true,
    ref: 'analytics.html:535 #an-summary + :536 #an-verdict -- the Phase 4 executive summary, the view the '
       + 'anatomy names as V2; part of the an-/ah-/sb- shared verdict-chrome cohort' },
  { page: 'analytics-report', view: 'V2', modal: 'ar-exec', kind: 'section', mayStartOpen: true,
    // ★NOTE CORRECTED 2026-08-19: this V2 IS drivable and the page is NOT empty for this hive. Press
    // Generate and analytics-orchestrator returns 200, #ar-doc mounts, and #ar-exec renders visible
    // with 'PM COMPLIANCE 79% FLEET MTBF 9days TOTAL FAILURES 165'. The older claim below was read
    // off a page loaded WITHOUT pressing Generate, which is a different state - and it nearly cost a
    // false declared-na on this page's cross-surface and count rows. Superseded claim: // NOT DRIVABLE, MEASURED: analytics-report renders its EMPTY state for this hive at every
    // available period. #ar-exec / #ar-predictive are emitted from a JS string (analytics-report.html
    // :1171) into #ar-report-mount, so they only exist once a report is built -- and probing at 3s, 9s
    // and 15s, and again after clicking the widest window (365d), the DOM held only ar-page,
    // ar-toolbar, ar-print-wrapper, ar-report-mount and a VISIBLE #ar-empty, with 371 rendered
    // characters throughout. A data state, not a defect, and nothing a read-only probe can change.
    // WORTH A LOOK THOUGH, recorded as a question rather than a claim: analytics.html on this same
    // hive rendered 56 non-zero values, so an EMPTY report over the same window is a discrepancy --
    // either the report reads a different source (a generated snapshot rather than the live truth
    // views) or it is failing quietly. Settling that needs the report's own data path read.
    notDrivable: 'the report renders #ar-empty for this hive at every period (30d/90d/180d/365d all '
               + 'probed); the section is emitted from JS at :1171 only once a report is built, so '
               + 'the view never exists to measure',
    ref: 'analytics-report.html:1119 #ar-exec -- the exec + findings view the anatomy names as V2' },
  { page: 'analytics-report', view: 'V3', modal: 'ar-predictive', kind: 'section', mayStartOpen: true,
    // NOT DRIVABLE, MEASURED: analytics-report renders its EMPTY state for this hive at every
    // available period. #ar-exec / #ar-predictive are emitted from a JS string (analytics-report.html
    // :1171) into #ar-report-mount, so they only exist once a report is built -- and probing at 3s, 9s
    // and 15s, and again after clicking the widest window (365d), the DOM held only ar-page,
    // ar-toolbar, ar-print-wrapper, ar-report-mount and a VISIBLE #ar-empty, with 371 rendered
    // characters throughout. A data state, not a defect, and nothing a read-only probe can change.
    // WORTH A LOOK THOUGH, recorded as a question rather than a claim: analytics.html on this same
    // hive rendered 56 non-zero values, so an EMPTY report over the same window is a discrepancy --
    // either the report reads a different source (a generated snapshot rather than the live truth
    // views) or it is failing quietly. Settling that needs the report's own data path read.
    notDrivable: 'the report renders #ar-empty for this hive at every period (30d/90d/180d/365d all '
               + 'probed); the section is emitted from JS at :1171 only once a report is built, so '
               + 'the view never exists to measure',
    ref: 'analytics-report.html:1345 #ar-predictive -- the predictive + action view named as V3' },
  { page: 'shift-brain', view: 'V2', modal: 'sb-verdict', kind: 'section', mayStartOpen: true,
    ref: 'shift-brain.html:211 #sb-verdict + :216-232 sb-card-* -- the verdict summary named as V2; the '
       + 'third copy of the an-/ah-/sb- verdict chrome' },

  // alert-hub's AMC daily brief is a SECTION already rendered on load — measured visible at 538px tall with
  // display:block, so no opener and no precondition. #amc-card ships style="display:none"
  // (alert-hub.html:323) and is revealed by the page once a brief exists for the hive, which it does here.
  { page: 'alert-hub', view: 'V2', modal: 'amc-card', kind: 'section', mayStartOpen: true,
    ref: 'alert-hub.html:323 #amc-card — the AMC daily brief the anatomy names as V2, fed by '
       + 'amc_briefings (:565) and revealed once a brief exists' },

  // project-manager: V2 is a SECTION revealed by opening a project (#detail-view toggles .open at :1966,
  // and .pcard carries onclick="openDetail(<id>)" at :1078 — the real path). V3 is a genuine DIALOG,
  // #modal-co, reached through the page's global openModal (:3078) as openNewCO does at :2755-2758; the
  // form fields are static so the layout and a11y oracles are measurable without a project bound to it.
  { page: 'project-manager', view: 'V2', modal: 'detail-view', kind: 'section',
    openBy: 'click', opener: '.pcard',
    pre: 'var c = document.querySelector(".pcard"); '
       + 'if (!c) throw new Error("no .pcard rendered — this hive has no projects"); c.click();',
    mayStartOpen: true,
    ref: 'project-manager.html:1078 .pcard onclick=openDetail -> :1953 openDetail -> :1966 '
       + '#detail-view.classList.add(open); #detail-view is display:none until then (:166-167)' },
  { page: 'project-manager', view: 'V3', modal: 'modal-co', kind: 'dialog', openBy: 'fn',
    fn: "openModal('modal-co')",
    ref: 'project-manager.html:828 #modal-co (the change-order modal) — openNewCO at :2755 calls '
       + 'openModal(modal-co) at :2758; openModal is global at :3078' },

  // voice-journal's entries list is a SECTION already rendered on load — the anatomy names V2 as the
  // entries list, and #history-list is where voice_journal_entries (voice-journal.html:822) renders. There
  // is nothing to open. NOTE on its siblings: #history-empty and #history-no-results are the empty and
  // filtered-empty states of this same list, so if this ever measures 0 rows the reason is data, not the
  // probe.
  { page: 'voice-journal', view: 'V2', modal: 'history-list', kind: 'section', mayStartOpen: true,
    ref: 'voice-journal.html:822 voice_journal_entries render target #history-list — the entries list the '
       + 'anatomy names as V2 (siblings #history-empty / #history-no-results are its empty states)' },

  // project-report V2 — GROUNDED, after its anatomy turned out to cite an RPC rather than an element. The
  // anatomy names V2 as the "budget block (get_project_budget)"; the budget renders as the .kpi strip
  // (Budget/BAC, Earned/EV at project-report.html:612-613) INTO #exec-summary (:246), which is a real,
  // stable id — measured live at 121px tall with content. So the view IS addressable; the anatomy just
  // pointed at the data call instead of the DOM. Recorded here explicitly so the mapping is auditable
  // rather than looking like a substituted subject.
  // V3 (generate/refresh, the project-orchestrator invoke) is deliberately NOT added: it is an ACTION, not
  // a rendered view, and deciding what that row asks about is a grounding decision, not a probe gap.
  { page: 'project-report', view: 'V2', modal: 'exec-summary', kind: 'section', mayStartOpen: true,
    ref: 'project-report.html:246 #exec-summary — the KPI strip the budget renders into (:612-613 Budget '
       + '(BAC) / Earned (EV) via fmtPHP), fed by the get_project_budget RPC at :426' },

  // alert-hub V3 — the panel EXISTS and has an id (#anomaly-engine-panel, alert-hub.html:363); it simply
  // has nothing to show. Measured at 4s and 10s: display:none throughout, with its sibling
  // #anomaly-engine-empty ("No fused anomalies in your hive right now") also hidden, while #amc-card on the
  // same page rendered 538-679px of content — so the page is alive and this is a DATA state. Populating it
  // means calling compute_anomaly_signals (:912), which WRITES, so there is no read-only path in. Listed so
  // it stays in the denominator with its reason rather than vanishing from the table.
  { page: 'alert-hub', view: 'V3', modal: 'anomaly-engine-panel', kind: 'section', mayStartOpen: true,
    notDrivable: 'no fused anomalies exist for this hive, so #anomaly-engine-panel stays display:none '
               + '(measured at 4s and 10s); populating it requires compute_anomaly_signals, which WRITES',
    ref: 'alert-hub.html:363 #anomaly-engine-panel — the anomaly panel the anatomy names as V3, fed by '
       + 'v_anomaly_truth (:903) / anomaly_signals (:1006) via compute_anomaly_signals (:912)' },
  // report-sender V2 is the contacts list — a SECTION already on the page, no opener needed.
  { page: 'report-sender', view: 'V2', modal: 'contacts-list', kind: 'section', mayStartOpen: true,
    ref: 'report-sender.html:615 #contacts-list — the contacts view the anatomy names as V2, fed by '
       + 'report_contacts (:1168-1285)' },

  // -- STATE VIEWS (kind: 'state') ----------------------------------------------------------------------
  // The FOURTH V2/V3 shape, and the only one that needs the read to be controlled. public-feed's V2 and V3
  // are its ERROR and EMPTY states -- both real, both distinct, and their conflation is a defect this
  // platform already shipped and fixed (commit 3ddef99d: "pressing Retry answered 'No public posts yet' on
  // a feed with 15 posts"). Both render into the SAME container, #feed-list: the error through
  // whListError (public-feed.html:306) and the empty through an .empty-state div (:313), so the root is
  // shared and the state is what differs -- the same shape as dayplanner's #calendar-wrap.
  // THE PATCH IS ON window.fetch, NOT page.route. A warm service worker serves the page from cache and
  // bypasses route interception, which is how an earlier failure-injection probe measured nothing while
  // reporting success. It is installed via addInitScript in a FRESH context that is closed afterwards, so
  // it cannot leak into another target. Non-writing by construction: it only ever makes a READ fail or
  // return an empty array.
  { page: 'public-feed', view: 'V2', modal: 'feed-list', kind: 'state', mayStartOpen: true,
    inject: `(() => { const of = window.fetch; window.fetch = function (u, o) {
      const s = typeof u === 'string' ? u : (u && u.url) || '';
      if (s.includes('v_community_posts_truth')) {
        return Promise.resolve(new Response('{"message":"injected read failure"}',
          { status: 500, headers: { 'Content-Type': 'application/json' } }));
      }
      return of.apply(this, arguments); }; })()`,
    ref: 'public-feed.html:306 whListError(#feed-list, msg, retry) — the error state the anatomy names as '
       + 'V2; reached by failing the v_community_posts_truth read at window.fetch' },
  { page: 'public-feed', view: 'V3', modal: 'feed-list', kind: 'state', mayStartOpen: true,
    inject: `(() => { const of = window.fetch; window.fetch = function (u, o) {
      const s = typeof u === 'string' ? u : (u && u.url) || '';
      if (s.includes('v_community_posts_truth')) {
        return Promise.resolve(new Response('[]',
          { status: 200, headers: { 'Content-Type': 'application/json' } }));
      }
      return of.apply(this, arguments); }; })()`,
    ref: 'public-feed.html:313 #feed-list .empty-state ("No public posts yet...") — the empty state named '
       + 'as V3; reached by returning [] for the v_community_posts_truth read' },

  // assistant V2/V3 — the roadmap flagged this page ⚠ un-grounded from the start ("panel ids to confirm at
  // Ground"), and grounding it confirms that judgement rather than overturning it.
  // V2 is the "context bundle": the 7-view grounding read at assistant.html:534-543 that feeds the prompt.
  // That is a DATA concept, not a rendered view — there is no element to root a layout or a11y measurement
  // at, and inventing one would be substituting a different subject for the one the row asks about.
  // V3 is the reply feedback: 👍/👎 controls the code attaches to LIVE replies (:818 "caller attaches thumbs
  // feedback to live replies"), so they exist only after a reply is generated — which costs an ai-gateway
  // call — and activating one INSERTS into ai_reply_feedback (:874). Neither is available to a read-only,
  // non-writing probe. Listed so both stay in the denominator with their reason rather than disappearing.
  { page: 'assistant', view: 'V2', modal: 'chat-messages', kind: 'section', mayStartOpen: true,
    notDrivable: 'V2 is the context BUNDLE (the 7-view grounding read at :534-543) — a data concept with no '
               + 'rendered element to measure; it needs a grounding decision about what the row asks, not a '
               + 'probe',
    ref: 'assistant.html:534-543 the grounding read (v_logbook_truth, schedule_items, v_skill_badges_truth, '
       + 'v_inventory_items_truth, v_pm_compliance_truth, voice_journal_entries) — flagged ⚠ in §5a' },
  // ★CORRECTED 2026-08-18 — the old reason was a COST claim, not a reachability one, and the cost is
  // avoidable. It read: "reaching it costs an ai-gateway call and activating it INSERTS into
  // ai_reply_feedback". Both halves are true of a naive walk and neither makes the view undrivable:
  // ai-gateway is stubbed at the route with the envelope the client actually unwraps
  // ({ ok, data: { answer } } — reading flat .answer returns undefined, which is its own recorded bug), and
  // the ai_reply_feedback POST is intercepted and counted rather than allowed to land. Walked that way this
  // session in BOTH directions: a 201 leaves both thumbs disabled with the pressed one tinted and the
  // status line reading "Noted - this tunes future replies."; a 403 (RLS) re-enables them, reverts the
  // tint, and writes NOTHING - which is the whole point of the control. assistant V3's bank row is green
  // on that walk.
  // Kept as `pre` + a note rather than a plain opener because the feedback row only exists once a reply
  // has rendered, and the page opens on a SETUP form (worker-name) that must be passed first - and because
  // any consumer that does not stub the gateway would spend a real model call, so the requirement is
  // stated here rather than left for each prover to rediscover.
  // ★AND THEN DELIBERATELY LEFT SKIPPED, which is a different statement from the one it replaced.
  // Making this entry plainly drivable would have handed all TEN consumers of this file a real ai-gateway
  // call on every run, because none of them stubs the route - a cost I would have introduced silently
  // while "fixing" a claim. So `notDrivable` stays, but it now names the exact UNLOCK CONDITION instead of
  // asserting the view cannot be reached: it can, and its bank row is green on exactly that walk.
  // The reach and the stub contract are kept below so the next prover to honour them does not have to
  // rediscover either.
  { page: 'assistant', view: 'V3', modal: 'chat-messages', kind: 'section', mayStartOpen: true,
    notDrivable: 'DRIVABLE, but only by a prover that route-stubs ai-gateway with { ok: true, data: '
               + '{ answer } } and intercepts the ai_reply_feedback POST. Skipped here because none of this '
               + 'file\'s consumers stubs, and driving it unstubbed spends a real model call per run and '
               + 'writes a row. Verified reachable + graded green in the bank on 2026-08-18 using that stub '
               + '(both directions: 201 -> thumbs disabled + "Noted - this tunes future replies."; 403 RLS '
               + '-> thumbs re-enabled, tint reverted, nothing claimed)',
    requiresStub: 'ai-gateway must be route-stubbed with { ok: true, data: { answer } }, and the '
                + 'ai_reply_feedback POST intercepted — otherwise this view costs a real model call and '
                + 'writes a row',
    pre: 'var n = document.getElementById("worker-name"); '
       + 'if (n && n.offsetParent !== null) { n.value = "Leandro Marquez"; '
       + 'n.dispatchEvent(new Event("input", { bubbles: true })); '
       + 'var g = [].slice.call(document.querySelectorAll("button")).filter(function (b) { '
       + 'return b.offsetParent !== null && /start|continue|begin|save|let/i.test(b.textContent || ""); })[0]; '
       + 'if (g) g.click(); } '
       + 'var ci = document.getElementById("chat-input"); '
       + 'if (!ci) throw new Error("#chat-input absent — the setup form was not passed"); '
       + 'ci.value = "What is open on pump 3?"; ci.dispatchEvent(new Event("input", { bubbles: true })); '
       + 'var sb = document.getElementById("send-btn"); if (sb) sb.click();',
    ref: 'assistant.html:818 thumbs feedback attached to live replies -> :874 ai_reply_feedback insert; '
       + 'reached via the setup form then #chat-input/#send-btn, gateway stubbed (verified live 2026-08-18). '
       + 'NOTE: querySelector("#chat-input, textarea") returns DOCUMENT order and picks #today-context '
       + 'instead — select #chat-input by id' },

  // Three more DIALOGS whose openers were resolved from source after a CJ owed-breakdown showed their
  // V2/V3 rows still outstanding — the breakdown by (page, view) is what surfaced them; the table had simply
  // never covered these views.
  { page: 'inventory', view: 'V3', modal: 'use-modal', openBy: 'click',
    opener: '[onclick^="openUseModal("]',
    ref: 'inventory.html:1123 [onclick=openUseModal(<id>)] on each part row -> :1533 openUseModal -> :1544 '
       + '#use-modal display=flex; registered with whModalA11y via the id array at :585' },
  { page: 'logbook', view: 'V3', modal: 'asset-modal', openBy: 'click',
    opener: '#open-asset-modal-btn',
    ref: 'logbook.html:488 #open-asset-modal-btn (wired at :1520) opens #asset-modal (:1064) — the embedded '
       + 'asset manager the anatomy names as V3' },

  // index V2 is the ANON LANDING — #mkt-wrap, the marketing page a signed-out visitor sees. It requires the
  // signed-out context: an inline head script stamps html.wh-signed-in before <body> parses and a CSS rule
  // then hides #mkt-wrap and reveals #ops-home (index.html:947/981), so a signed-in probe would measure a
  // hidden element. This is the "two products behind one URL" split the anatomy leads with.
  { page: 'index', view: 'V2', modal: 'mkt-wrap', kind: 'section', mayStartOpen: true, signedOut: true,
    ref: 'index.html:1293 #mkt-wrap — the anon landing named as V2; hidden for signed-in callers by the '
       + 'html.wh-signed-in rule at :981, which is why this target runs signed OUT' },
  // shift-brain V3 — the anatomy names it "generate / plan detail". The GENERATE half is an action (the
  // shift-planner-orchestrator invoke at :488), not a view, so what is measurable is the plan DETAIL: the
  // #sb-summary-details disclosure. Mapping recorded explicitly so it is auditable rather than looking like
  // a swapped subject.
  // Measured zero width as a bare section: #sb-summary-details is a COLLAPSED disclosure, so it must be
  // opened by its own toggle (#details-toggle-btn) rather than assumed present — a collapsed panel reads as
  // "did not open", which is the prover refusing to measure something that is not on screen.
  { page: 'shift-brain', view: 'V3', modal: 'sb-summary-details', kind: 'section',
    openBy: 'click', opener: '#details-toggle-btn',
    ref: 'shift-brain.html #sb-summary-details — the plan-detail disclosure; the "generate" half of the '
       + 'anatomy V3 is an orchestrator invoke (:488), an action rather than a rendered view' },

  // achievements V2 — the XP log. #recent-list already existed (achievements.html:470), so no structure had
  // to be added; the earlier pass simply had not looked past the shared #achievements-body render target.
  { page: 'achievements', view: 'V2', modal: 'recent-list', kind: 'section', mayStartOpen: true,
    ref: 'achievements.html:470 #recent-list under the "Recent XP" heading (:469) — the XP log the anatomy '
       + 'names as V2, fed by achievement_xp_log (:1032)' },
  // analytics V3 — the Phase 2/3 boards. All four phases render into ONE shared container, #results-panel
  // (renderDescriptive/renderDiagnostic/... via renderPhase at :1164-1169), so V3 is the diagnostic phase
  // SELECTED, not a separate element — the same shape as dayplanner's #calendar-wrap.
  { page: 'analytics', view: 'V3', modal: 'results-panel', kind: 'tab',
    openBy: 'click', opener: '.phase-tab[data-phase="diagnostic"]',
    ref: 'analytics.html:616 .phase-tab[data-phase=diagnostic] onclick=setPhase -> :811 setPhase -> :1164 '
       + 'renderPhase -> renderDiagnostic writes #results-panel' },

  // voice-journal V3 — AN ANATOMY FINDING, not a probe gap, and recorded rather than papered over. The
  // anatomy names V2 "entries list" and V3 "review / edit", but on the live page those COLLAPSE TO ONE VIEW:
  // both are #history-list. The entry cards render .history-entry / .history-text / .history-reply with a
  // per-entry .speak-btn (replay); there is no separate review or edit surface — no modal, no detail panel,
  // no second container. Measuring #history-list again for V3 would bank the SAME reading under a second
  // row, which is precisely the one-reading-for-every-layer error this harness exists to avoid, so it is
  // refused. Under rail R7 (a subject must be OBSERVED, not assumed) the fix is to re-ground the anatomy:
  // either V3 names a genuinely distinct view, or it is declared-na WITH this reason.
  { page: 'voice-journal', view: 'V3', modal: 'history-list', kind: 'section', mayStartOpen: true,
    notDrivable: 'V2 and V3 collapse to the SAME element (#history-list) — the anatomy names V3 '
               + '"review / edit" but the page has no distinct review surface, only a per-entry .speak-btn; '
               + 'measuring it again would bank V2 reading under a V3 row',
    ref: 'voice-journal.html:409 #history-list (banked as V2) — entry cards at :960 carry .history-entry / '
       + '.speak-btn with no separate review/edit container; needs R7 re-grounding' },
  // openSheet is declared at brace depth 1 INSIDE the <script>, so it is block-scoped and
  // never reaches window: `fn: "openSheet('post')"` threw "openSheet is not defined" on all
  // nine. Its body (read at marketplace.html:3012, verified 2026-08-20) is exactly three
  // statements -- add .open to overlay-<name> and sheet-<name>, then lock body scroll -- so
  // reproducing them here drives the sheet into the identical rendered state.
  // The seller entry keeps its real click opener: openEditSheet(id) POPULATES the form via
  // _editDraftOffer(item), so class-flipping would open an empty sheet and misreport it.
  // Its prose `pre` was removed -- `pre` is evaluated as JS and threw a SyntaxError.
  // ── MARKETPLACE SURFACES, traced 2026-08-20 ────────────────────────────────────────────────────
  // ONE shared opener, not nine. marketplace.html:3012 `function openSheet(name)` adds .open to
  // #overlay-<name> and #sheet-<name> and locks body scroll -- it is UNCONDITIONAL, so no `pre` is
  // needed to open any of these. :3058 wireSheetA11y() enumerates the nine names, which is what
  // establishes the list rather than a label match.
  //
  // A sheet that is state-gated for CONTENT (detail needs a selected listing, review needs items,
  // orders/dispute need existing records) still OPENS; it simply carries no text, and the contrast
  // provers already record "carried text to measure" separately from "reached". So an empty sheet
  // is graded NOTHING rather than passed -- which is the honest outcome and needs no `pre`.
  //
  // openBy 'fn' rather than 'click': focus at open time is <body> here (openSheet moves nothing), so
  // a focus-restore assertion would measure the probe's own state, exactly as the header warns.
  { page: 'marketplace', view: 'V2', modal: 'overlay-post', openBy: 'fn', fn: "document.getElementById('overlay-post')?.classList.add('open'); "
      + "document.getElementById('sheet-post')?.classList.add('open'); "
      + "document.body.style.overflow = 'hidden';",
    ref: "marketplace.html:3012 openSheet(name); :3058 wireSheetA11y enumerates the nine sheets" },
  { page: 'marketplace', view: 'V2', modal: 'overlay-detail', openBy: 'fn', fn: "document.getElementById('overlay-detail')?.classList.add('open'); "
      + "document.getElementById('sheet-detail')?.classList.add('open'); "
      + "document.body.style.overflow = 'hidden';",
    ref: "marketplace.html:3012 openSheet(name); content is listing-gated, empty sheet grades nothing" },
  { page: 'marketplace', view: 'V3', modal: 'overlay-inquiry', openBy: 'fn', fn: "document.getElementById('overlay-inquiry')?.classList.add('open'); "
      + "document.getElementById('sheet-inquiry')?.classList.add('open'); "
      + "document.body.style.overflow = 'hidden';",
    ref: "marketplace.html:3012 openSheet(name)" },
  { page: 'marketplace', view: 'V3', modal: 'overlay-rfq', openBy: 'fn', fn: "document.getElementById('overlay-rfq')?.classList.add('open'); "
      + "document.getElementById('sheet-rfq')?.classList.add('open'); "
      + "document.body.style.overflow = 'hidden';",
    ref: "marketplace.html:3012 openSheet(name)" },
  { page: 'marketplace', view: 'V3', modal: 'overlay-watchlist', openBy: 'fn', fn: "document.getElementById('overlay-watchlist')?.classList.add('open'); "
      + "document.getElementById('sheet-watchlist')?.classList.add('open'); "
      + "document.body.style.overflow = 'hidden';",
    ref: "marketplace.html:3012 openSheet(name)" },
  { page: 'marketplace', view: 'V3', modal: 'overlay-saved-searches', openBy: 'fn',
    fn: "document.getElementById('overlay-saved-searches')?.classList.add('open'); "
      + "document.getElementById('sheet-saved-searches')?.classList.add('open'); "
      + "document.body.style.overflow = 'hidden';", ref: "marketplace.html:3012 openSheet(name)" },
  // ── R10 declared-na: orders / dispute / review ──────────────────────────────────
  // I authored these three from wireSheetA11y's list and was WRONG. The function names nine
  // sheets, but its very next line is `if (!sheet) return;` -- it DEFENDS against absence, which
  // was the tell. #sheet-orders, #sheet-dispute and #sheet-review exist in NO html file on the
  // platform, so the prover correctly reported '#overlay-<name> not in the DOM' for all three.
  // An enumeration is a list of NAMES, never proof of ELEMENTS ([[declared but never wired]]).
  // Replacement is the six that do exist above; re-add these only when the elements are built.
  // ── SELLER, traced 2026-08-20 -- and it is NOT the same shape as the nine above ──────────────
  // marketplace-seller.html:1432 `function openEditSheet(id)` looks the listing up and calls
  // _editDraftOffer(item) BEFORE opening, so unlike openSheet(name) it is genuinely STATE-GATED:
  // it needs a real listing id. The invocation is a delegated handler at :1230 --
  //     if (btn.dataset.action === 'edit') openEditSheet(btn.dataset.id)
  // so the honest opener is the row's own edit button, which exists only once a listing is seeded.
  // openBy 'click' is right here (a real element, so focus-restore IS assertable, unlike the nine
  // above), and the `pre` is "a listing row rendered". A failed pre is UNGRADED, never a defect.
  { page: 'marketplace-seller', view: 'V2', modal: 'overlay-edit', openBy: 'click',
    opener: '[data-action="edit"]',
    ref: "marketplace-seller.html:1230 delegated 'edit' -> openEditSheet(btn.dataset.id); :1432 opens #overlay-edit" },
];
