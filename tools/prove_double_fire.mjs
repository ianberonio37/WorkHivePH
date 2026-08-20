// prove_double_fire.mjs — CO `double_tap` + CK `component_busy`, on ONE harness.
//
// THE TWO ORACLES ARE THE SAME EVENT SEEN FROM TWO SIDES:
//   CO double_tap    — "the second press changes nothing further and the surface says so"
//   CK component_busy — "an in-flight control is busy and cannot be re-fired"
// Both are answered by pressing a control twice while its write is still in flight, so they share a run.
//
// ★WHY THIS IS SAFE, AND WHY THAT MATTERS MORE HERE THAN ANYWHERE ELSE IN THE ARC.
// Every other oracle in this bank can be answered by LOOKING. This one can only be answered by ACTING —
// and a probe that acts on a live product performs the thing it meant to observe. That is not
// hypothetical: a previous sweep on this platform went hunting for a refusal and ACTIVATED A SUCCESS,
// because its filter excluded delete/pay but not save/generate, and populated forms submitted for real
// ([[feedback_hunting_a_refusal_i_activated_a_success]]).
//
// So the write never leaves the browser. `fetch` is replaced in an addInitScript, which runs BEFORE
// supabase-js constructs its client and ABOVE the service worker — the same mechanism the failure
// injection prover uses, and the reason it is trusted. Any mutating request (POST/PATCH/PUT/DELETE to
// /rest/v1/, /rpc/, or /functions/) is COUNTED and then hangs forever, never resolving. Nothing is
// created, updated, paid or deleted; the row this probe would have written does not exist. GET is left
// completely alone so the page still loads its data normally.
//
// HANGING IS ALSO THE HONEST STIMULUS. A double-tap guard only matters WHILE a write is in flight — if
// the request completes in 40ms locally, a human could never press twice inside the window and the test
// would pass for the wrong reason. Holding the request open makes the in-flight window the whole test.
//
// ★A CONTROL THAT FIRES NO WRITE IS UNGRADED, NEVER FAILED. Most buttons open a modal, switch a tab or
// expand a section. If pressing produced zero mutating requests, this oracle has no subject on that page
// and the run says so — the same rule the failure injection prover uses for a zero-hit page. Reporting
// "no double-fire guard" about a control that never submits anything is a fabricated defect.
//
// Usage:
//   node tools/prove_double_fire.mjs                 # all pages with a mapped control
//   node tools/prove_double_fire.mjs --page logbook
//   node tools/prove_double_fire.mjs --selftest      # teeth, both directions, no product involved
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

// ★PROCESS DEADLINE. This prover deliberately stubs writes with `new Promise(() => {})` -- a
// never-settling promise, which is the CORRECT semantic for blocking a write during a probe
// (rejecting would drive the page's error path; resolving 200 would make the page believe the
// write landed). But page.evaluate() has no default timeout in Playwright, so if the page's own
// JS awaits that stubbed write inside an evaluate, nothing ever settles and the whole SUITE
// stops. suite_v4 died exactly that way on prove_failure_injection: 584 of 585 verdicts, 17
// minutes of silence, 0.30 CPU-seconds across every node+chrome process. A promise that never
// settles is invisible -- no error, no output, no exit.
// .unref() so this never delays a clean finish; it only fires if we are STILL running at the
// deadline. Budget derived from THIS prover's own flow (PAGES x ~54s worst case), not copied -- a constant borrowed
// from a prover with a different settle profile either fires spuriously or never fires.
const WATCHDOG_MS = 1500_000;
setTimeout(() => {
  console.error(`WATCHDOG: exceeded ${WATCHDOG_MS}ms without finishing -- treating as HUNG, not slow.`);
  process.exit(3);
}, WATCHDOG_MS).unref();

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// The interceptor. Counts mutating requests and never lets them finish.
// letThrough: URL fragments that must NOT be hung. Supabase .rpc() reads are POSTs, so a shim that hangs
// every mutating request also starves a page's own READ path - on pm-scheduler, get_pm_compliance_smrp and
// get_pm_ontime_delivery are awaited before the asset cards render, so blanket-hanging them left the page
// with zero cards and my reach reporting "no .asset-card rendered". Same shape as the blanket 429 that
// starved project-report's load, and the fix is the same: scope the injection to the action under test.
// Each entry is DECLARED PER FLOW with its reason, never inferred from the name - compute_anomaly_signals
// looks like a read and writes.
const HANG_WRITES = (letThrough) => {
  window.__whWrites = { count: 0, urls: [] };
  const of = window.fetch;
  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = String(
      (init && init.method) || (input && input.method) || 'GET'
    ).toUpperCase();
    const mutating = ['POST', 'PATCH', 'PUT', 'DELETE'].includes(method);
    const apiish = /\/rest\/v1\/|\/rpc\/|\/functions\/v1\//.test(url);
    const exempt = (letThrough || []).some((frag) => url.includes(frag));
    // ★TELEMETRY IS NOT THE ACTION. analytics_events is this platform's click-logging table, and it fires on
    // presses that do nothing else - so counting it as a write made a GUARDED control look unguarded: on
    // analytics the recompute correctly refused its second press (button disabled, no second
    // batch-risk-scoring) while the second click still logged one telemetry row, and the count read 1 -> 2.
    // Verified against the page directly first: same node, disabled true after press one, no second action
    // request. It is still HELD like any other write - it just does not count as the action having fired twice.
    const telemetry = /analytics_events/.test(url);
    if (mutating && apiish && !exempt && !telemetry) {
      window.__whWrites.count++;
      if (window.__whWrites.urls.length < 6) window.__whWrites.urls.push(method + ' ' + url.slice(-60));
      return new Promise(() => {});           // hangs forever: the write never lands
    }
    if (mutating && apiish && telemetry) {
      // held, not counted: nothing reaches the database either way
      return new Promise(() => {});
    }
    return of.apply(this, arguments);
  };
};

// Controls whose press should attempt a write. Harvested from the pages themselves rather than guessed:
// the verb list is what this product actually puts on its submit buttons.
const WRITE_VERB = /^(save|send|add|submit|log|complete|create|post|publish|confirm|generate|apply|record|update)\b/i;

// ── PER-PAGE FLOWS ────────────────────────────────────────────────────────────────────────────────
// The verb scan only ever reaches TOP-LEVEL buttons, and on 11 of 12 pages those merely OPEN a form.
// A submit control that needs its form opened and filled first has to be REACHED, so each flow lists the
// steps to get there. Steps run with writes already intercepted, so every click along the way is as safe
// as the double-press itself.
//
// ★TOGGLES ARE DELIBERATELY EXCLUDED. community's reaction buttons are directly clickable and DO write —
// but a second press legitimately UN-reacts, so "the second press changes nothing further" is false by
// design there, and grading them would manufacture a defect out of correct behaviour. This oracle is
// about SUBMIT-shaped actions, where the second press must be absorbed.
// ★SOME CONTROLS ONLY ANSWER AN IN-PAGE CLICK. On asset-hub a Playwright click on .asset-card is intercepted
// and does nothing while element.click() opens the detail; shift-brain's plan-body controls behave the same
// way - they sit thousands of pixels below the fold (publish measured at y=3221 on a 390x844 viewport) and a
// coordinate click never reached their handlers, so a working action read as "produced no mutating request".
// A flow can therefore declare pressVia: 'dom' and the press is dispatched through the element itself. This
// is stated per flow rather than applied globally, because a coordinate click is the more faithful gesture
// where it works - it is the one that catches an occluded or unreachable control.
async function press(page, sel, via) {
  if (via === 'dom') {
    const ok = await page.evaluate((s) => {
      const e = document.querySelector(s);
      if (!e) return false;
      e.click();
      return true;
    }, sel);
    if (!ok) throw new Error(`pressVia dom: ${sel} matched nothing`);
    return;
  }
  await page.click(sel, { force: true, timeout: 5000 });
}

const FLOWS = {
  // The platform's one irreversible OUTWARD action, and so the place a missing double-fire guard costs
  // the most: a plant's numbers sent twice to a manager cannot be un-sent.
  'report-sender': {
    steps: [
      { click: 'button:has-text("PM Overdue")', why: 'select a report chip so there is something to send' },
      // updateSendBtn() keeps #send-btn DISABLED until a report AND a recipient exist, so without this
      // the probe clicked a dead control and reported "produced no mutating request" — a false UNGRADED
      // about the one action that most needed grading.
      { fill: '#email-input', value: 'probe@example.com', why: 'a recipient is required to enable the send' },
    ],
    submit: 'button:has-text("Send Reports")',
    note: 'irreversible outward send — the highest-stakes double-fire on the platform',
  },
  // A planned item. The modal ships its own Save, so the submit is reachable once the required title
  // exists. Everything typed here is discarded with the context; the write is held and never lands.
  dayplanner: {
    steps: [
      { click: 'button:has-text("+ Schedule")', why: 'open the schedule-item modal' },
      { fill: '#m-title', value: 'wh double-fire probe', why: 'the item needs a title to be saveable' },
    ],
    submit: '#modal button:has-text("Save"), button:has-text("Save")',
    note: 'schedule_items insert — a queued write, so a double-fire would drain as two rows',
  },
  // Asset registration. The modal's own submit repeats the opener's label, so the selector is scoped
  // INSIDE the modal — clicking the page-level button would just re-open the dialog and grade nothing.
  logbook: {
    steps: [
      { click: 'button:has-text("Register Asset")', why: 'open the asset-registration modal' },
      { fill: '#a-asset-id', value: 'WH-PROBE-DF', why: 'asset id is required' },
      { fill: '#a-name', value: 'double-fire probe asset', why: 'asset name is required' },
    ],
    // NAMED BY ID, because "Register Asset" appears THREE times on this page — the page-level opener,
    // the modal's TAB (#asset-tab-register), and the actual submit. A text match found the tab and merely
    // switched tabs, which fired no write and reported a false UNGRADED. Every flow here names its submit
    // by id for exactly this reason.
    submit: '#asset-submit-btn',
    note: 'asset_nodes insert — feeds v_asset_truth and 11 downstream consumers, so a duplicate is costly',
  },
  // A spare part. The modal's submit is #part-submit-btn ("Save Part") — named explicitly rather than
  // matched by text, because the page also carries Use/Restock submits and a text match could press the
  // wrong one, which on a stock-critical surface is not a harmless mistake.
  inventory: {
    steps: [
      { click: 'button:has-text("Add Part")', why: 'open the part modal' },
      { fill: '#f-part-number', value: 'WH-DF-PROBE', why: 'part number identifies the row' },
      { fill: '#f-part-name', value: 'double-fire probe part', why: 'name is required' },
      { fill: '#f-qty', value: '1', why: 'a quantity is required to save a stock row' },
    ],
    submit: '#part-submit-btn',
    note: 'inventory_items insert — stock-critical, and a duplicate row corrupts the on-hand balance',
  },
  // A PM asset. Unlike the others this is a FOUR-STEP WIZARD, so the submit is only reachable after the
  // whole walk — which is why a top-level press reported a false UNGRADED. Step 1 validates silently:
  // with name/tag/location/category unset the Next button clicks and the step simply does not advance,
  // showing no error, so the walk must fill them before advancing.
  // The COMPLETION SHEET (V2) - pm-scheduler's own acting view, distinct from the Add-Asset wizard above.
  // Reached the way the UI reaches it: OPEN an asset (markDone reads currentAsset.asset_name and throws
  // without one), then complete a scope item BELONGING TO THAT ASSET - any other item is refused by the RLS
  // policy pm_completions_scope_parent_guard, correctly, since that would be a cross-parent write.
  // hive's INTENT CAPTURE (V3) - the first-run modal, already open at load, so there is no opener. POLLED
  // rather than asserted at one instant: it is raised after the board's own loads settle, and a fixed 4.2s
  // check read "already answered this session" when the truth was that I looked too early.
  // report-sender's CONTACTS sheet (V2). Opened with #add-contact-btn; the send sheet (V3) reuses the same
  // #sheet-overlay, so the two views are told apart by which form is inside it, not by the overlay.
  'report-sender-contacts': { page: 'report-sender',
    steps: [{ wait: 3000 },
            { click: '#add-contact-btn' },
            { wait: 900 },
            { fill: '#contact-name', value: 'WH Probe Contact' },
            { fill: '#contact-email', value: 'wh.probe@example.com' }],
    submit: '#save-contact-btn' },
  // inventory's USE sheet (V3) - the stock-drawing action, distinct from the part-modal (V2) above.
  'inventory-use': { page: 'inventory',
    steps: [{ wait: 2500, why: 'the parts list must render before a Use button exists' },
            { click: 'button:has-text("Use")' },
            { wait: 900 },
            { fill: '#use-qty', value: '1' }],
    submit: '#use-submit-btn' },
  // dayplanner's WEEK view (V2). Distinct from V1's "+ Schedule" button: here the action starts from a
  // per-slot "Add task on <day> at <hour>" control, so the slot's own date and time are carried into the
  // shared item modal. Both views render into #calendar-wrap, so the reach PROVES the switch took
  // (#logo-view == 'Week') before hunting for a slot - a silently ignored switch would act on the day grid
  // and file the result against the week.
  'dayplanner-week': { page: 'dayplanner',
    steps: [{ wait: 3000 },
            { eval: "(async () => { if (typeof switchView !== 'function') throw new Error('switchView is not defined'); switchView('wilo'); const l = document.getElementById('logo-view'); if (!l || l.textContent.trim() !== 'Week') throw new Error('the week view did not take'); const t0 = Date.now(); while (Date.now() - t0 < 9000) { const b = [...document.querySelectorAll('#calendar-wrap button, #calendar-wrap [role=button]')].find((e) => ((e.getAttribute('aria-label') || e.textContent || '').trim().toLowerCase().startsWith('add task')) && e.offsetParent !== null); if (b) { b.click(); return; } await new Promise((r) => setTimeout(r, 250)); } throw new Error('no visible Add-task slot button appeared in the week grid within 9s'); })()" },
            { wait: 1000 },
            { fill: '#m-title', value: 'week slot probe' }],
    submit: 'button:has-text("Save")' },
  // community's THREAD OVERLAY (V2) - the post with its replies and reactions, distinct from the composer
  // (V3) graded separately. Reached through a post's own "Open thread and reply" control, then PROVEN open
  // before anything is measured, because a silently missed click would grade the feed and file it against
  // the thread.
  'community-thread': { page: 'community',
    steps: [{ wait: 2500 },
            { eval: "(async () => { const t0 = Date.now(); while (Date.now() - t0 < 9000) { const b = [...document.querySelectorAll('button, [role=button]')].find((e) => (e.getAttribute('aria-label') || '').toLowerCase().indexOf('open thread') === 0 && e.offsetParent !== null); if (b) { b.click(); await new Promise((r) => setTimeout(r, 900)); const o = document.getElementById('thread-overlay'); if (!o || getComputedStyle(o).display === 'none') throw new Error('the thread overlay did not open'); return; } await new Promise((r) => setTimeout(r, 250)); } throw new Error('no Open-thread control appeared within 9s'); })()" },
            { fill: '#reply-content', value: 'probe reply' }],
    submit: '#btn-submit-reply' },
  // skillmatrix's EXAM modal (V3) - a credential-bearing write, the highest-stakes action in the roster:
  // a badge here is a claim about someone's qualifications. Reached the long way on purpose, through the
  // lesson modal's own start control and then ANSWERING all ten questions, because submitExam only fires
  // when every answer is set - setting _examAnswers directly would prove nothing about the exam a person
  // actually takes.
  'skillmatrix-exam': { page: 'skillmatrix',
    steps: [{ wait: 3000 },
            { eval: "(async () => { const wait = (ms) => new Promise((r) => setTimeout(r, ms)); const until = async (fn, ms) => { const t = Date.now();   while (Date.now() - t < ms) { const v = fn(); if (v) return v; await wait(150); } return null; }; if (typeof openLesson !== 'function') throw new Error('openLesson is not defined'); const KEY = (typeof SKILL_CONTENT !== 'undefined' && Object.keys(SKILL_CONTENT)[0]) || 'Mechanical'; if (!SKILL_CONTENT[KEY] || !SKILL_CONTENT[KEY]['1'] || !(SKILL_CONTENT[KEY]['1'].exam || []).length)   throw new Error('no exam content for ' + KEY + ' level 1'); openLesson(KEY, 1); const lm = await until(() => { const m = document.getElementById('lesson-modal');   return m && getComputedStyle(m).display !== 'none' ? m : null; }, 9000); if (!lm) throw new Error('the lesson modal did not open'); const start = document.getElementById('lesson-exam-btn'); if (!start) throw new Error('#lesson-exam-btn is not in the DOM'); if (!start.disabled) throw new Error('the exam button was ENABLED before the lesson was read - the read-before-tested gate is not holding'); const scrollEl = document.getElementById('lesson-body-scroll'); if (!scrollEl) throw new Error('#lesson-body-scroll is not in the DOM'); scrollEl.scrollTop = scrollEl.scrollHeight; scrollEl.dispatchEvent(new Event('scroll', { bubbles: true })); const enabled = await until(() => (!start.disabled ? true : null), 6000); if (!enabled) throw new Error('the exam button stayed disabled after scrolling the lesson to the bottom'); start.click(); const ready = await until(() => (typeof _examQuestions !== 'undefined' && _examQuestions   && _examQuestions.length ? true : null), 6000); if (!ready) throw new Error('the Take-Exam click left 0 questions'); const em = await until(() => { const m = document.getElementById('exam-modal');   return m && getComputedStyle(m).display !== 'none' ? m : null; }, 9000); if (!em) throw new Error('the exam modal did not open'); let answered = 0; for (let i = 0; i < 15; i++) {   const opts = await until(() => { const o = document.querySelectorAll('#exam-options-wrap .exam-option');     return o.length ? o : null; }, 6000);   if (!opts) break;   const correct = (_examQuestions[_currentQuestion] || {}).answer;   const pick = (typeof correct === 'number' && opts[correct]) ? opts[correct] : opts[0];   pick.click(); answered++;   const nb = await until(() => { const b = document.getElementById('exam-next-btn');     return b && !b.disabled ? b : null; }, 4000);   if (!nb) break;   if (/submit|finish/i.test((nb.textContent || ''))) break;   const before = document.querySelector('#exam-options-wrap .exam-option');   nb.click();   await until(() => document.querySelector('#exam-options-wrap .exam-option') !== before, 4000); } if (answered < 1) throw new Error('answered no questions'); window.__whExamAnswered = answered; })()" }],
    submit: '#exam-next-btn' },
  // project-manager's CHANGE ORDER (V3) - a financial + approval write, and the one form on this page that
  // must state its effect on BOTH budget and schedule (it carries #co-cost in PHP and #co-days). Reached
  // through the detail view's own "+ Raise change order" control, with both the detail and the dialog PROVEN
  // open before anything is measured.
  'project-manager-co': { page: 'project-manager',
    steps: [{ wait: 2500 },
            { eval: "(async () => { const wait = (ms) => new Promise((r) => setTimeout(r, ms)); const until = async (fn, ms) => { const t = Date.now();   while (Date.now() - t < ms) { const v = fn(); if (v) return v; await wait(200); } return null; }; const card = await until(() => document.querySelector('.pcard'), 9000); if (!card) throw new Error('no .pcard appeared within 9s'); card.click(); const dv = await until(() => { const d = document.getElementById('detail-view');   return d && getComputedStyle(d).display !== 'none' ? d : null; }, 9000); if (!dv) throw new Error('the project detail did not open'); const raise = await until(() => [...document.querySelectorAll('button')].find((e) => /raise change order/i.test((e.textContent || '')) && e.offsetParent !== null), 9000); if (!raise) { if (typeof openNewCO !== 'function') throw new Error('no Raise-change-order control and openNewCO is undefined'); openNewCO(); } else raise.click(); const m = await until(() => { const x = document.getElementById('modal-co');   return x && getComputedStyle(x).display !== 'none' ? x : null; }, 9000); if (!m) throw new Error('#modal-co did not open'); })()" },
            { fill: '#co-title', value: 'probe change order' },
            { fill: '#co-scope', value: 'probe scope change: add two anchor restraints' }],
    submit: '#form-co button[type=submit]' },
  // asset-hub's WEIBULL tab (V3). The fit goes through the weibull-fitter EDGE function, and the page claims
  // a downstream ripple only when the fit is defensible - so the walk needs a faithful fit response, not an
  // echoed request, or it grades the insufficient-data consolation sentence instead.
  'asset-hub-weibull': { page: 'asset-hub',
    steps: [{ wait: 2500 },
            // THE WORKBENCH IS OPT-IN. #reliability-card ships display:none behind an explicit "Show
            // Reliability Workbench (engineer view)" toggle, so the Weibull tab measures zero size until it
            // is revealed — the same three gates the FMEA flow on this page already traced. Opting in here
            // rather than rediscovering it.
            { click: '#asset-view-toggle' },
            { wait: 600 },
            { eval: "(async () => { const wait = (ms) => new Promise((r) => setTimeout(r, ms)); const until = async (fn, ms) => { const t = Date.now();   while (Date.now() - t < ms) { const v = fn(); if (v) return v; await wait(200); } return null; }; const card = await until(() => document.querySelector('.asset-card'), 9000); if (!card) throw new Error('no .asset-card appeared within 9s'); card.click(); await wait(1500); const tgl = document.getElementById('asset-view-toggle'); if (tgl) { tgl.click(); await wait(800); } const tab = await until(() => [...document.querySelectorAll('[data-tab]')].find((e) => e.getAttribute('data-tab') === 'weibull'), 9000); if (!tab) throw new Error('no Weibull tab found'); tab.click(); await wait(1200); const fit = await until(() => { const b = document.getElementById('weibull-fit-btn');   return b && !b.disabled && b.offsetParent !== null ? b : null; }, 9000); if (!fit) throw new Error('#weibull-fit-btn not reachable after opening the Weibull tab'); })()" }],
    submit: '#weibull-fit-btn' },
  // index's SIGN-IN modal (V3). Revealed directly rather than through openSignIn(), which checks for a stored
  // worker name and toggles the USER MENU instead when one exists - so on the signed-in context these provers
  // establish, the real opener never reaches this dialog. Stated rather than hidden: this measures the dialog's
  // own behaviour, not the opener's.
  'index-signin': { page: 'index',
    steps: [{ wait: 2500 },
            { eval: "(() => { const m = document.getElementById('signin-modal'); if (!m) throw new Error('#signin-modal is not in the DOM'); m.classList.remove('hidden'); if (m.classList.contains('hidden')) throw new Error('the sign-in modal stayed hidden'); })()" },
            { wait: 600 },
            { fill: '#si-username', value: 'wh.probe.user' },
            { fill: '#si-password', value: 'wh-probe-password' }],
    submit: '#panel-signin button[type=submit]' },
  // alert-hub's INBOX (V1). The dismissal is delegated on .alert-dismiss and branches three ways by data
  // attribute - data-seen-key acknowledges, data-snooze-key snoozes 7 days, and a bare data-dismiss-key marks
  // handled. This flow deliberately targets the MARK-HANDLED branch, which is the one that writes
  // alert_dismissals keyed on (hive_id, alert_key) and therefore hides the alert for the whole hive; the probe
  // stamps an id on the found control so the press has a stable target.
  'alert-hub-dismiss': { page: 'alert-hub',
    steps: [{ wait: 3000 },
            { eval: "(async () => { const wait = (ms) => new Promise((r) => setTimeout(r, ms)); const until = async (fn, ms) => { const t = Date.now();   while (Date.now() - t < ms) { const v = fn(); if (v) return v; await wait(200); } return null; }; const btn = await until(() => [...document.querySelectorAll('.alert-dismiss[data-dismiss-key]')].find((e) => e.offsetParent !== null && !e.getAttribute('data-seen-key') && !e.getAttribute('data-snooze-key')), 12000); if (!btn) throw new Error('no visible .alert-dismiss[data-dismiss-key] in the inbox within 12s'); window.__whDismissKey = btn.getAttribute('data-dismiss-key'); btn.setAttribute('data-wh-probe', 'dismiss'); })()" }],
    submit: '[data-wh-probe=dismiss]' },
  // analytics V1's one committing action: the batch-risk-scoring recompute. Everything else on this page
  // draws existing rows. The control already guards itself (an early return when disabled), which is what
  // the double-press row measures.
  'analytics-recompute': { page: 'analytics',
    steps: [{ wait: 3500 },
            { eval: "(async () => { const wait = (ms) => new Promise((r) => setTimeout(r, ms)); const until = async (fn, ms) => { const t = Date.now();   while (Date.now() - t < ms) { const v = fn(); if (v) return v; await wait(200); } return null; }; if (typeof setPhase !== 'function') throw new Error('setPhase is not defined'); setPhase('predictive'); const b = await until(() => { const e = document.getElementById('recompute-risk-btn');   return e && e.offsetParent !== null && !e.disabled ? e : null; }, 15000); if (!b) throw new Error('#recompute-risk-btn never appeared after setPhase(predictive) - it is rendered by renderPredictive(), not present in static markup'); b.setAttribute('data-wh-probe', 'recompute'); })()" }],
    // MEASURED: with rpc/get_pm_ontime_delivery held, the counted requests were
    // [get_pm_ontime_delivery, batch-risk-scoring, batch-risk-scoring] - the page's own READ was starved,
    // which let the panel come back enabled and the second press genuinely fire again. Read RPCs arrive as
    // POSTs, so a write-holding shim starves them unless they are named. Third page where this pattern bit.
    letThrough: ['rpc/get_pm_ontime_delivery'],
    submit: '[data-wh-probe=recompute]' },
  // resume's BUILDER (V1). Its committing control is #btn-save -> saveCloud(), which is why this page reported
  // zero commit controls on a bare load: the button is not reachable until the builder has something to save.
  // A data-* attribute is stamped rather than an id, because overwriting an id is how a probe silently breaks
  // a page's own guard (analytics looked its button up by id to disable it).
  'resume-save': { page: 'resume',
    steps: [{ wait: 3500 },
            { eval: "(async () => { const wait = (ms) => new Promise((r) => setTimeout(r, ms)); const until = async (fn, ms) => { const t = Date.now();   while (Date.now() - t < ms) { const v = fn(); if (v) return v; await wait(200); } return null; }; const b = await until(() => { const e = document.getElementById('btn-save');   return e && e.offsetParent !== null && !e.disabled ? e : null; }, 12000); if (!b) throw new Error('#btn-save never became reachable within 12s'); const f = document.getElementById('rb-field-name'); if (f) { f.value = 'WH Probe Engineer';   f.dispatchEvent(new Event('input', { bubbles: true }));   f.dispatchEvent(new Event('change', { bubbles: true })); } b.setAttribute('data-wh-probe', 'resume-save'); })()" }],
    submit: '[data-wh-probe=resume-save]' },
  // shift-brain's PUBLISH (the plan leaves draft and becomes the crew's instruction). Guarded in shipped code:
  // supervisor-only, disables before the write, re-enables on failure. Needs BOTH a supervisor and an active
  // plan to be reachable, so the reach waits rather than asserting at one instant.
  'shift-brain-publish': { page: 'shift-brain',
    steps: [{ wait: 4000 },
            { eval: "(async () => { const wait = (ms) => new Promise((r) => setTimeout(r, ms)); const until = async (fn, ms) => { const t = Date.now();   while (Date.now() - t < ms) { const v = fn(); if (v) return v; await wait(200); } return null; }; const b = await until(() => { const e = document.getElementById('publish-btn');   const ready = (typeof _activePlan !== 'undefined') && _activePlan;   return e && e.offsetParent !== null && !e.disabled && ready ? e : null; }, 16000); if (!b) throw new Error('#publish-btn never became reachable - it needs a supervisor AND an active plan'); b.setAttribute('data-wh-probe', 'publish'); })()" }],
    pressVia: 'dom',   // measured: a coordinate click never reached publishPlan (y=3221, below the fold)
    submit: '[data-wh-probe=publish]' },
  // shift-brain's GENERATE / RE-RUN (V3) - the orchestrator rebuild. Supervisor-only, and the control names
  // itself 'Running...' while in flight. Whichever of #rerun-btn / #generate-btn is present is used, since
  // both are wired to the same handler.
  'shift-brain-generate': { page: 'shift-brain',
    steps: [{ wait: 4000 },
            { eval: "(async () => { const wait = (ms) => new Promise((r) => setTimeout(r, ms)); const until = async (fn, ms) => { const t = Date.now();   while (Date.now() - t < ms) { const v = fn(); if (v) return v; await wait(200); } return null; }; const b = await until(() => { const e = document.getElementById('rerun-btn') || document.getElementById('generate-btn');   return e && e.offsetParent !== null && !e.disabled ? e : null; }, 16000); if (!b) throw new Error('neither #rerun-btn nor #generate-btn became reachable'); b.setAttribute('data-wh-probe', 'sb-generate'); })()" }],
    // MEASURED: a coordinate click never reached rerunPlan (zero mutating requests) while the handler has no
    // early return past its supervisor check, and a DOM click on the same control fires the invoke. This
    // page's plan-body controls sit far below the fold - publish measured at y=3221 - which is the same
    // interception the asset-hub flow documented.
    pressVia: 'dom',
    submit: '[data-wh-probe=sb-generate]' },
  // pm-scheduler's EDIT modal (V3). Supervisor-only and pre-filled from currentAsset, so the reach opens an
  // asset first (openEditPMAsset dereferences currentAsset.asset_name and throws without one) and then renames
  // it, so there is a real change to save. The read RPCs this page awaits are let through, because a
  // write-holding shim starves them and the schedule renders zero asset cards.
  'pm-scheduler-edit': { page: 'pm-scheduler',
    steps: [{ wait: 3000 },
            { eval: "(async () => { const wait = (ms) => new Promise((r) => setTimeout(r, ms)); const until = async (fn, ms) => { const t = Date.now();   while (Date.now() - t < ms) { const v = fn(); if (v) return v; await wait(200); } return null; }; const c = await until(() => document.querySelector('.asset-card'), 12000); if (!c) throw new Error('no .asset-card rendered'); c.click(); await wait(1500); if (typeof currentAsset === 'undefined' || !currentAsset) throw new Error('no asset opened'); if (typeof openEditPMAsset !== 'function') throw new Error('openEditPMAsset is not defined'); openEditPMAsset(); await wait(700); const m = document.getElementById('pm-edit-modal'); if (!m || getComputedStyle(m).display === 'none') throw new Error('the edit modal did not open - HIVE_ROLE may not be supervisor'); const n = document.getElementById('pm-edit-name'); if (n) { n.value = 'WH Probe Renamed Asset'; n.dispatchEvent(new Event('input', { bubbles: true })); } })()" }],
    letThrough: ['rpc/get_pm_compliance_smrp', 'rpc/get_pm_ontime_delivery'],
    submit: '#pm-edit-save-btn' },
  'hive-intent': { page: 'hive',
    steps: [
      { eval: "(async () => { const t0 = Date.now(); while (Date.now() - t0 < 9000) { const m = document.getElementById('intent-capture'); if (m && getComputedStyle(m).display !== 'none' && document.querySelectorAll('input[name=\"intent-primary\"]').length) return; await new Promise((r) => setTimeout(r, 250)); } throw new Error('the intent modal never opened within 9s'); })()",
        why: 'wait for the first-run modal the board raises' },
      { eval: "(() => { const r = document.querySelector('input[name=\"intent-primary\"]'); if (!r) throw new Error('no intent-primary radio'); r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); })()",
        why: 'choose a goal so the save has something to commit' },
    ],
    // MEASURED: with this hung the board never finished loading and the modal never opened at all.
    letThrough: ['rpc/get_hive_board_dashboard'],
    submit: '#intent-save' },
  'pm-scheduler-complete': { page: 'pm-scheduler',
    steps: [
      { wait: 4500, why: 'scopeItems and the asset list must load before either is reachable' },
      // Clicked through an eval that THROWS when the card is missing, because a plain click step is
      // .catch(() => {})-swallowed here - and a silently skipped click reads downstream as "no asset opened",
      // which is indistinguishable from a page defect until you instrument it.
      { eval: "(() => { const c = document.querySelector('.asset-card'); if (!c) throw new Error('no .asset-card rendered'); c.click(); })()",
        why: 'sets currentAsset, which markDone dereferences' },
      { wait: 2500, why: 'the asset opens and loads its own scope' },
      { eval: "(() => { if (typeof currentAsset === 'undefined' || !currentAsset) throw new Error('no asset opened'); const aid = currentAsset.id; const mine = scopeItems.filter(i => i && i.id && i.asset_id === aid); if (!mine.length) throw new Error('the opened asset has no scope item to complete'); markDone(mine[0].id); if (!document.getElementById('completion-sheet').classList.contains('open')) throw new Error('markDone ran but the sheet did not open'); })()",
        why: 'open the completion sheet on an in-scope item' },
      { wait: 1200, why: 'the sheet paints and markDone resets #sheet-findings' },
      { fill: '#sheet-findings', value: 'probe: checked, within tolerance', why: 'the findings a tech would type' },
    ],
    // MEASURED, not guessed: with these two hung, the page rendered 0 asset cards while scopeItems held 144.
    // Both are read-only compliance RPCs the schedule render awaits; the completion write itself is
    // pm_completions + logbook, and those stay hung, which is what this oracle needs.
    letThrough: ['rpc/get_pm_compliance_smrp', 'rpc/get_pm_ontime_delivery'],
    submit: '#sheet-save-btn' },
  'pm-scheduler': {
    steps: [
      { click: '#tab-add', why: 'open the Add Asset wizard' },
      { fill: '#w-name', value: 'WH DF Probe Asset', why: 'step 1 will not advance without a name' },
      { fill: '#w-tag', value: 'WH-DF-PM', why: 'asset tag' },
      { fill: '#w-location', value: 'Probe Bay', why: 'location' },
      { select: '#w-category', index: 1, why: 'a category must be chosen for step 1 to validate' },
      { advance: 3, why: 'walk steps 1->2->3->4 until #btn-save-asset is reachable' },
    ],
    submit: '#btn-save-asset',
    note: 'pm_assets insert — a duplicate PM asset double-counts the compliance denominator',
  },
  // The AI companion. Pressing send calls the ai-gateway edge function, which is a MUTATING request in
  // every sense that matters here: it costs a model call and appends a turn. A double-fire spends the
  // quota twice and can interleave two replies into one thread.
  assistant: {
    steps: [
      { fill: '#chat-input', value: 'double-fire probe', why: 'the composer must hold text for send to fire' },
    ],
    submit: '#send-btn',
    note: 'ai-gateway invoke — a double-fire spends the model quota twice',
  },
  // A hive post. Community's REACTION buttons are excluded from this oracle as toggles, but the COMPOSER
  // is genuinely submit-shaped: one press, one post. #btn-submit-post lives inside #composer-overlay,
  // opened by the #fab-post floating button.
  community: {
    steps: [
      { click: '#fab-post', why: 'open the composer sheet' },
      { fill: '#post-content', value: 'double-fire probe post', why: 'a post needs content to submit' },
    ],
    submit: '#btn-submit-post',
    note: 'community_posts insert — a duplicate post is visible to the whole hive',
  },
  // The mic. Tap to start, tap to stop, then the transcribe call runs; the subject is a THIRD tap while
  // that call is in flight. Reachable only because the context supplies a fake audio device.
  'voice-journal': {
    steps: [
      { click: '#mic-btn', why: 'start recording (fake audio device supplies the stream)' },
      { wait: 2400, why: 'let the recorder capture the fixture' },
      { click: '#mic-btn', why: 'stop, which kicks off voice-transcribe' },
      { wait: 1500, why: 'be mid-transcribe when the double-press lands' },
    ],
    submit: '#mic-btn',
    note: 'voice-transcribe then voice_journal_entries — a re-fire costs a second transcription',
    // THE WRITE FIRES DURING THE STEPS, NOT ON THE SUBMIT. Stopping the recording is what kicks off
    // voice-transcribe, so by the time the "submit" press lands the request is already in flight and the
    // press under test is the RE-press. Zeroing the counter first made the third tap look like a control
    // that fires nothing at all, and the row reported UNGRADED against a page whose guard demonstrably
    // works. So this flow keeps the steps' write as press one.
    countFromSteps: true,
  },
  // The CAPTURE modal — seven gates deep, and the subject double_tap actually cares about on this page: a
  // duplicated logbook entry poisons MTBF, PM compliance and a person's resume evidence, because
  // v_logbook_truth feeds eleven consumers.
  // ★A PLAIN CLICK, DELIBERATELY. The handler sets saveBtn.disabled = true on entry, so the disabled
  // button IS the guard here — and form.requestSubmit() bypasses a disabled submitter entirely. Using it
  // would have measured past the protection and reported a double-fire that cannot happen to a person.
  // Verified separately that a click reaches the listener identically to requestSubmit, so nothing is lost.
  'logbook-capture': { page: 'logbook',
    steps: [{ eval: "document.getElementById('asset-picker-btn') && document.getElementById('asset-picker-btn').click()" },
            { wait: 1200 },
            { eval: "(() => { const m = document.getElementById('asset-picker-modal'); if (!m) return; const r = [...m.querySelectorAll('button,li,[role=option],div[data-asset-id]')].find(e => { const s = getComputedStyle(e); return s.display !== 'none' && e.getBoundingClientRect().height > 0 && (e.innerText || '').trim().length > 2; }); if (r) r.click(); })()" },
            { wait: 900 },
            { eval: "(() => { const b = [...document.querySelectorAll('button')].find(e => /what happened/i.test(e.innerText || '')); if (b) b.click(); })()" },
            { wait: 900 },
            { fill: '#f-problem', value: 'probe: drive tripped on overload' },
            { fill: '#f-root-cause', value: 'probe: loose terminal' },
            { eval: "(() => { for (const id of ['f-maint-type','f-category','f-wo-state']) { const e = document.getElementById(id); if (e && e.options && e.options.length > 1) { e.selectedIndex = 1; e.dispatchEvent(new Event('change', { bubbles: true })); } } })()" },
            { wait: 500 },
            { eval: "(() => { const b = [...document.querySelectorAll('button')].find(e => /what did you do/i.test(e.innerText || '')); if (b) b.click(); })()" },
            { wait: 900 },
            { fill: '#f-action', value: 'probe: retightened the terminal and reset the drive' },
            { eval: "(() => { const b = document.querySelector('.consequence-btn[data-value]'); if (b) b.click(); })()" },
            { wait: 500 }],
    submit: '#save-entry-btn',
    note: 'logbook insert — a duplicate entry poisons MTBF, PM compliance and resume evidence',
  },
  // An FMEA failure mode. The FMEA table is the queue-adopter on this page, so a double-fire here would
  // not just duplicate a row — it would duplicate a row that DRAINS LATER, and RPN is recomputed from
  // its factors, so a doubled mode skews the asset's risk ranking.
  'asset-hub': {
    steps: [
      // THREE GATES, EACH FOUND BY TRACING RATHER THAN GUESSING. (1) #fmea-add-btn lives inside an asset
      // DETAIL, so the roster must be opened first — pressing it from the list threw "element is not
      // visible". (2) A Playwright .asset-card click is INTERCEPTED and does nothing, while an in-page
      // element.click() opens the detail correctly, so the open is dispatched in-page. (3) Even then the
      // FMEA tabs measured zero size while computing display:flex — walking the ancestor chain found
      // #reliability-card at display:none, gated behind an explicit "Show Reliability Workbench (engineer
      // view)" toggle (#asset-view-toggle, aria-controls="reliability-card"). The workbench is opt-in, so
      // the flow must opt in.
      { eval: "document.querySelector('.asset-card') && document.querySelector('.asset-card').click()",
        why: 'open an asset detail (in-page click; a Playwright click is intercepted here)' },
      { click: '#asset-view-toggle', why: 'reveal #reliability-card, which ships display:none' },
      { click: '[data-tab="fmea"]', why: 'switch to the FMEA tab where the add control lives' },
      { click: '#fmea-add-btn', why: 'open the FMEA mode modal' },
      { fill: '#fmea-function', value: 'double-fire probe function', why: 'the mode needs a function' },
      { fill: '#fmea-failure-mode', value: 'probe failure mode', why: 'and a failure mode' },
    ],
    submit: '#fmea-save',
    note: 'rcm_fmea_modes insert — a QUEUED write feeding RPN, so a duplicate skews the risk ranking',
  },
};

const FIND_CONTROL = (verbSrc) => {
  const re = new RegExp(verbSrc, 'i');
  const vis = (e) => {
    const s = getComputedStyle(e); const b = e.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.01
      && b.width > 0 && b.height > 0;
  };
  const cands = [...document.querySelectorAll('button, [role="button"], input[type="submit"]')]
    .filter((e) => vis(e) && !e.disabled && e.getAttribute('aria-disabled') !== 'true')
    .filter((e) => re.test(((e.innerText || e.textContent || '').trim())));
  if (!cands.length) return null;
  const e = cands[0];
  if (!e.id) e.setAttribute('data-wh-df', '1');
  return { sel: e.id ? '#' + e.id : '[data-wh-df="1"]',
           label: ((e.innerText || e.textContent || '').trim()).slice(0, 40) };
};

const READ_STATE = (sel) => {
  const e = document.querySelector(sel);
  if (!e) return { gone: true, writes: (window.__whWrites || { count: 0 }).count };
  const cs = getComputedStyle(e);
  // ★A HIDDEN CONTROL IS AS UNREACHABLE AS A REMOVED ONE, and missing that produced a false FAIL against
  // a page whose defence is the best kind. dayplanner CLOSES the modal on save: the write fires, the
  // dialog goes, and the second press cannot land at all — Playwright's click threw because the button
  // was not visible. But the button still EXISTS in the DOM inside the hidden modal, so a `gone` test
  // based on querySelector returning null saw it as present-and-silent and reported "no in-flight
  // signal". Removing the control IS the signal; it is the strongest form of "the surface says so".
  const rect = e.getBoundingClientRect();
  const hidden = cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity < 0.02
    || rect.width === 0 || rect.height === 0;
  const txt = ((e.innerText || e.textContent || '').trim()).slice(0, 60);
  return {
    gone: false,
    hidden,
    disabled: e.disabled === true || e.getAttribute('aria-disabled') === 'true',
    busy: e.getAttribute('aria-busy') === 'true',
    dimmed: +cs.opacity < 0.85 || /not-allowed/.test(cs.cursor) || cs.pointerEvents === 'none',
    text: txt,
    // "the surface SAYS so" — the platform's own in-flight wording, on the CONTROL, in a live region, or
    // in a TOAST. The toast was a real blindspot: this platform answers a blocked wizard step with
    // showToast('Please enter an asset name.'), and a scan restricted to the control and to
    // [id*=error]/[class*=error] saw none of it — which had me report a page as validating SILENTLY when
    // it says exactly what is missing. A message a person can read is a message, wherever it is mounted.
    saysWorking: /saving|sending|working|please wait|in progress|submitting|posting|generating|\.\.\.|…/i
      .test(txt) || !!document.querySelector('[aria-busy="true"]')
      || (() => {
        const t = document.querySelector('#toast, [id*="toast"], [class*="toast"], [role="status"], [role="alert"]');
        if (!t) return false;
        const ts = getComputedStyle(t); const tb = t.getBoundingClientRect();
        const shown = ts.display !== 'none' && ts.visibility !== 'hidden' && +ts.opacity > 0.05
          && tb.width > 0 && tb.height > 0;
        return shown && /saving|sending|working|please wait|in progress|submitting|posting|generating/i
          .test((t.innerText || '').trim());
      })(),
    writes: (window.__whWrites || { count: 0 }).count,
  };
};

if (args.includes('--selftest')) {
  // TEETH, both directions, against planted controls — no product write path is involved at all.
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 390, height: 844 } });
  await c.addInitScript(HANG_WRITES, []);
  const pg = await c.newPage();
  await pg.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  let fail = 0;
  // A GUARDED control: disables itself on first press, so a second press cannot fire again.
  // An UNGUARDED one: fires every time — the double-submit this oracle exists to catch.
  await pg.evaluate(() => {
    // OFFSET, because both fixtures at top:0;left:0 OVERLAP and the click lands on whichever is painted
    // last — which made the GUARDED button report two writes that the UNGUARDED one had actually fired.
    let n = 0;
    const mk = (id, guarded) => {
      const btn = document.createElement('button');
      btn.id = id; btn.textContent = 'Save';
      btn.style.cssText = `position:fixed;top:${n++ * 60}px;left:0;width:120px;height:44px;z-index:99999`;
      btn.addEventListener('click', () => {
        if (guarded && btn.disabled) return;
        if (guarded) { btn.disabled = true; btn.textContent = 'Saving…'; }
        fetch('/rest/v1/thing', { method: 'POST', body: '{}' });
      });
      document.body.appendChild(btn);
    };
    mk('wh-df-good', true); mk('wh-df-bad', false);
  });
  const press2 = async (sel) => {
    await pg.evaluate((s) => { window.__whWrites.count = 0; }, sel);
    await pg.click(sel, { force: true }); await pg.waitForTimeout(120);
    await pg.click(sel, { force: true }); await pg.waitForTimeout(120);
    return pg.evaluate(READ_STATE, sel);
  };
  const good = await press2('#wh-df-good');
  if (good.writes !== 1) { console.log(`  FAIL — a GUARDED control fired ${good.writes} writes on two presses`); fail++; }
  else console.log(`  ok — guarded control fired exactly 1 write on two presses, and says "${good.text}"`);
  if (!good.disabled && !good.saysWorking) { console.log('  FAIL — guarded control gave the surface no in-flight signal'); fail++; }
  else console.log('  ok — guarded control shows its in-flight state (disabled/aria-busy/wording)');
  const bad = await press2('#wh-df-bad');
  if (bad.writes !== 2) { console.log(`  FAIL — an UNGUARDED double-submit was not caught (writes=${bad.writes})`); fail++; }
  else console.log('  ok — unguarded double-submit CAUGHT (2 writes from 2 presses)');
  // And the safety claim itself: nothing ever left the browser.
  const leaked = await pg.evaluate(() => window.__whWrites.urls.length > 0
    && window.__whWrites.urls.every((u) => u.startsWith('POST')));
  if (!leaked) { console.log('  FAIL — the interceptor did not record the writes it was meant to hold'); fail++; }
  else console.log('  ok — every write was COUNTED and HELD in the browser; none reached the server');
  await b.close();
  console.log(fail ? `\n  SELFTEST FAILED (${fail})`
    : '\n  SELFTEST PASSED — catches an unguarded double-submit, clears a guarded one, and proves no write escaped');
  process.exit(fail ? 1 : 0);
}

const PAGES = ONE ? [ONE] : ['logbook', 'inventory', 'pm-scheduler', 'pm-scheduler-complete', 'hive-intent', 'pm-scheduler-edit', 'shift-brain-generate', 'shift-brain-publish', 'resume-save', 'analytics-recompute', 'alert-hub-dismiss', 'index-signin', 'asset-hub-weibull', 'project-manager-co', 'skillmatrix-exam', 'community-thread', 'dayplanner-week', 'inventory-use', 'report-sender-contacts', 'dayplanner', 'asset-hub',
  'community', 'voice-journal', 'report-sender', 'project-manager', 'skillmatrix', 'assistant', 'hive'];

// ★A FAKE AUDIO DEVICE, because voice-journal has no button to fill in — its write is AUDIO-DRIVEN
// (mic -> voice-transcribe -> extraction -> voice_journal_entries), so no amount of form-filling reaches
// it. Chromium can play a WAV file as the microphone, which turns an "un-probeable" page into an
// ordinary one: --use-file-for-fake-audio-capture with a generated 2s tone (tools/make_probe_wav.py).
// This is the build-the-structure move rather than declaring the page covered-by-nature.
const LAUNCH_ARGS = ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream',
  '--use-file-for-fake-audio-capture=.tmp/probe.wav%noloop'];
const browser = await chromium.launch({ args: LAUNCH_ARGS });
const report = { ran: new Date().toISOString(), origin: ORIGIN, pages: {} };
for (const p of PAGES) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 },
                                         permissions: ['microphone'] });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  await ctx.addInitScript(HANG_WRITES, (FLOWS[p] && FLOWS[p].letThrough) || []);
  const page = await ctx.newPage();
  const rec = { page: p };
  try {
    await page.goto(`${ORIGIN}/${(FLOWS[p] && FLOWS[p].page) || p}.html`,
                    { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(4200);
    let ctl = null;
    const flow = FLOWS[p];
    if (flow) {
      for (const st of flow.steps) {
        if (st.eval) {
        // DO NOT SWALLOW A FAILED REACH. A swallowed eval error made this prover report "the page
        // produced no action" three runs in a row when the truth was that MY setup step had thrown
        // (markDone needs an open asset). A broken reach must read as UNGRADED, never as a page defect.
          await page.evaluate(st.eval).catch((e) => {
            throw new Error('setup step failed: ' + String(e && e.message || e).slice(0, 120));
          });
        } else if (st.wait) {
          await page.waitForTimeout(st.wait);
        } else if (st.fill) {
          await page.fill(st.fill, st.value, { timeout: 6000 }).catch(() => {});
        } else if (st.select) {
          // A native select needs its change event dispatched, or the wizard never sees the choice.
          await page.evaluate(({ sel, idx }) => {
            const e = document.querySelector(sel);
            if (e && e.options && e.options.length > idx) {
              e.selectedIndex = idx; e.dispatchEvent(new Event('change', { bubbles: true }));
            }
          }, { sel: st.select, idx: st.index }).catch(() => {});
        } else if (st.advance) {
          for (let i = 0; i < st.advance; i++) {
            await page.evaluate(() => {
              const b = [...document.querySelectorAll('button')]
                .find((e) => /^next/i.test((e.innerText || '').trim()) && !e.disabled && e.offsetParent !== null);
              if (b) b.click();
            }).catch(() => {});
            await page.waitForTimeout(800);
          }
        } else {
          await page.click(st.click, { timeout: 6000 }).catch(() => {});
        }
        await page.waitForTimeout(500);
      }
      const el = page.locator(flow.submit).first();
      if (await el.count()) {
        await el.evaluate((e) => e.setAttribute('data-wh-df', '1')).catch(() => {});
        ctl = { sel: '[data-wh-df="1"]',
                label: ((await el.innerText().catch(() => '')) || flow.submit).trim().slice(0, 40) };
        rec.flow = flow.note;
      }
    }
    if (!ctl) ctl = await page.evaluate(FIND_CONTROL, WRITE_VERB.source);
    if (!ctl) {
      rec.status = 'UNGRADED'; rec.why = 'no visible enabled control with a write verb on this page';
    } else {
      rec.control = ctl.label; rec.sel = ctl.sel;
      let after1;
      if (flow && flow.countFromSteps) {
        // The in-flight request from the steps IS the first fire; read state without re-pressing.
        after1 = await page.evaluate(READ_STATE, ctl.sel);
      } else {
        await page.evaluate(() => { window.__whWrites.count = 0; });
        await press(page, ctl.sel, flow && flow.pressVia);
        await page.waitForTimeout(400);
        after1 = await page.evaluate(READ_STATE, ctl.sel);
      }
      await press(page, ctl.sel, flow && flow.pressVia).catch(() => {});
      await page.waitForTimeout(400);
      const after2 = await page.evaluate(READ_STATE, ctl.sel);
      rec.writesAfter1 = after1.writes; rec.writesAfter2 = after2.writes;
      // Name the requests that were counted. A bare 1 -> 2 cannot be told apart from a duplicate ACTION and
      // an unrelated request the press happened to trigger, and those need opposite responses.
      rec.countedUrls = await page.evaluate(() => (window.__whWrites && window.__whWrites.urls) || []);
      rec.state1 = after1;
      if (after1.writes === 0) {
        rec.status = 'UNGRADED';
        rec.why = `pressing "${ctl.label}" produced no mutating request — it opens a view or validates a `
          + 'form rather than submitting, so this oracle has no subject here';
      } else {
        const held = after2.writes === after1.writes;
        // "The surface says so" is satisfied by any of: the control disables, marks itself busy, dims,
        // changes its wording, or BECOMES UNREACHABLE (removed from the DOM or hidden with its dialog).
        const says = after1.disabled || after1.busy || after1.dimmed || after1.saysWorking
          || after1.hidden || after2.gone || after2.hidden;
        rec.status = (held && says) ? 'PASS' : 'FAIL';
        rec.why = held
          ? (says ? `second press fired no further write (${after1.writes}) and the surface showed it`
                  + (after1.hidden || after2.hidden ? ' (the control became unreachable)' : '')
                  : `second press fired no further write, but the surface gave NO in-flight signal`)
          : `the second press fired ANOTHER write (${after1.writes} -> ${after2.writes})`;
      }
    }
  } catch (e) {
    rec.status = 'UNGRADED'; rec.why = 'probe error: ' + String(e).slice(0, 90);
  }
  report.pages[p] = rec;
  const tag = rec.status === 'PASS' ? 'PASS' : rec.status === 'FAIL' ? 'FAIL' : 'UNGRADED';
  console.log(`  ${p.padEnd(17)} ${tag.padEnd(9)} ${rec.control ? '"' + rec.control + '" ' : ''}${rec.why || ''}`.slice(0, 160));
  await ctx.close();
}
writeFileSync('double_fire_report.json', JSON.stringify(report, null, 1));
const g = Object.values(report.pages);
console.log(`\n  wrote double_fire_report.json — ${g.filter((x) => x.status === 'PASS').length} pass, `
  + `${g.filter((x) => x.status === 'FAIL').length} fail, ${g.filter((x) => x.status === 'UNGRADED').length} ungraded`);
console.log('  NO WRITE REACHED THE DATABASE: every mutating request was counted and held inside the page.');
await browser.close();
