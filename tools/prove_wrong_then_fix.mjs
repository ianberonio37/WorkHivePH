// prove_wrong_then_fix.mjs — CO `wrong_then_fix`: "a wrong entry can be corrected without starting over."
//
// THE FAILURE THIS CATCHES IS ORDINARY AND EXPENSIVE. Someone fills a form on a phone, in a plant, with
// gloves on. One field is wrong or missing. They submit. If the refusal wipes what they typed, they do
// not carefully re-enter it — they abandon the task, or they type less next time. The cost never shows up
// as an error in a log; it shows up as thinner data.
//
// HOW IT IS MEASURED, AND WHY THIS ONE NEEDS NO SYNTHETIC SUCCESS.
//   1. Open the form and fill every field EXCEPT one required field.
//   2. Submit. The page should REFUSE — this is a validation path, so nothing is written and no
//      interception is even needed for safety here; the write never happens.
//   3. Read back every field that WAS filled. They must still hold what was typed.
//   4. Supply the missing field and submit again — with writes intercepted, so the recovery is proven
//      without a row being created.
// The claim is step 3: the correction is a one-field fix, not a re-entry.
//
// ★A REFUSAL THAT SAYS NOTHING FAILS TOO. "Corrected without starting over" presumes the person knows
// WHAT to correct. A form that silently declines to advance preserves the typing perfectly and still
// leaves them stuck, so the refusal must also be legible — checked against the live surface, including
// toasts, because this platform answers a blocked step with showToast() and an earlier probe of mine
// scanned only [id*=error]/[class*=error] and reported a page as silent when it plainly was not.
//
// UNGRADED, NEVER FAILED, when the submit is not actually refused: if the page accepts the form with the
// field missing, this oracle has no refusal to recover from. That is a different finding (a missing
// required-field guard) and belongs to a different row — recording it here would be judging one thing by
// another oracle's evidence.
//
// Usage:
//   node tools/prove_wrong_then_fix.mjs
//   node tools/prove_wrong_then_fix.mjs --page inventory
//   node tools/prove_wrong_then_fix.mjs --selftest
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

// letThrough: URL fragments that must NOT be hung. Supabase .rpc() reads are POSTs, so hanging every
// mutating request also starves a page's own READ path — pm-scheduler awaits get_pm_compliance_smrp and
// get_pm_ontime_delivery before rendering a single asset card, so blanket-hanging them left this prover
// reporting "no .asset-card rendered" as though the page were broken. Declared per flow, with the
// measurement as the reason, never inferred from the name.
const HANG_WRITES = (letThrough) => {
  window.__whW = { count: 0 };
  const of = window.fetch;
  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = String((init && init.method) || 'GET').toUpperCase();
    const exempt = (letThrough || []).some((frag) => url.includes(frag));
    if (!exempt && ['POST', 'PATCH', 'PUT', 'DELETE'].includes(method)
        && /\/rest\/v1\/|\/rpc\/|\/functions\/v1\//.test(url)) {
      window.__whW.count++;
      return new Promise(() => {});
    }
    return of.apply(this, arguments);
  };
};

// ★WHAT DOES A TAP AT THIS CONTROL'S CENTRE ACTUALLY HIT? force:true dispatches at the element's centre
// point and SKIPS the actionability check, so an occluded button still "clicks" — the event just goes to
// whatever is painted on top. On pm-scheduler that was #wh-guide-link's <a href="/learn/...">, so the press
// NAVIGATED THE PAGE, every field read back null, and this prover reported "the refusal DESTROYED what had
// already been typed" about a page that had done nothing wrong. Null is not empty, and an unreachable
// control is not a defective one: an occluded submit is now UNGRADED with the occluder NAMED, which is how
// the real bug (a fixed page-guide chip sitting on every modal's action row) became findable at all.
// flow.submit is sometimes a PLAYWRIGHT selector (button:has-text("Save")). document.querySelector throws a
// SyntaxError on those, which cost dayplanner its verdict entirely — read disabled state through a locator.
async function isDisabled(page, sel) {
  const loc = page.locator(sel).first();
  if (!(await loc.count())) return false;
  return loc.evaluate((e) => e.disabled === true || e.getAttribute('aria-disabled') === 'true');
}

async function occludedBy(page, sel) {
  // Through Playwright's locator, NOT document.querySelector, for two reasons my first version got wrong:
  //  (1) elementFromPoint only sees the VIEWPORT, and Playwright scrolls a control into view before
  //      clicking it — so a button at y=2096 read as "nothing is hit-testable" and this guard invented
  //      three unreachable controls on pages that were fine. Scroll first, then hit-test.
  //  (2) flow.submit may be a Playwright selector like button:has-text("Save"), which querySelector
  //      rejects outright — dayplanner failed with a SyntaxError rather than a verdict.
  const loc = page.locator(sel).first();
  if (!(await loc.count())) return { why: 'selector matched nothing' };
  await loc.scrollIntoViewIfNeeded({ timeout: 4000 }).catch(() => {});
  const box = await loc.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) return { why: 'the control has no box (width/height 0)' };
  return loc.evaluate((el) => {
    const r = el.getBoundingClientRect();
    const cx = Math.round(r.left + r.width / 2), cy = Math.round(r.top + r.height / 2);
    if (cx < 0 || cy < 0 || cx > innerWidth || cy > innerHeight) return null;  // outside the viewport even
    const hit = document.elementFromPoint(cx, cy);                              // after scrolling: not our call
    if (!hit) return null;
    if (hit === el || el.contains(hit) || hit.contains(el)) return null;
    let owner = hit, id = null;
    while (owner) { if (owner.id) { id = owner.id; break; } owner = owner.parentElement; }
    return { why: `a tap at its centre (${cx}, ${cy}) lands on <${hit.tagName.toLowerCase()}> inside `
      + (id ? '#' + id : 'an unidentified element') + ' — the control is covered' };
  });
}

const READ_FIELDS = (sels) => {
  const out = {};
  for (const s of sels) {
    const e = document.querySelector(s);
    out[s] = e ? (e.value === undefined ? (e.textContent || '').trim() : e.value) : null;
  }
  return out;
};

const REFUSAL_NODES = () => {
  const vis = (e) => {
    const s = getComputedStyle(e); const b = e.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05
      && b.width > 0 && b.height > 0;
  };
  // Everything a person could actually read, wherever it is mounted — a toast counts.
  // MATCHED ON THE STEM, NOT THE WHOLE WORD: an element id-ed "...-err" is as much a refusal as "-error".
  const nodes = [...document.querySelectorAll(
    '#toast, [id*="toast"], [class*="toast"], [role="alert"], [role="status"], [aria-live],'
    + ' [id*="err"], [class*="err"], [id*="required"], [class*="required"], [id*="hint"]')];
  // ★PER NODE, KEYED — not one concatenated string. hive's board carries a dozen aria-live source chips
  // ("AI summary · refreshed daily · Based on your AI reports · ..."), so joining them produced a ~2KB
  // blob in which a 3-second toast was a needle, and one instant's read of that blob compared equal to the
  // read before it. The refusal then scored as SILENT on a page that says "Pick one to save, or tap Later."
  // clearly, for 3 seconds, at 188x66. Keying by node makes the refusal the node that CHANGED, which no
  // amount of unrelated live-region chatter can drown.
  // textContent, not innerText: innerText has returned '' for plainly visible controls on this platform.
  return nodes.map((e, i) => ({
    key: (e.id ? '#' + e.id : (e.getAttribute('role') || e.tagName.toLowerCase()) + ':' + i),
    text: (e.textContent || '').trim().slice(0, 300),
    shown: vis(e),
  }));
};

// The refusal is what APPEARED or CHANGED after the press — folded across several samples, because a toast
// that lives 3s can be gone by the time a fixed wait elapses, and a fixed wait is my timing, not the page's.
async function refusalDiff(page, before, samples = [250, 600, 1200, 2000]) {
  const seen = new Map(before.filter((n) => n.shown).map((n) => [n.key, n.text]));
  const found = new Map();
  let waited = 0;
  for (const at of samples) {
    await page.waitForTimeout(Math.max(0, at - waited)); waited = at;
    const now = await page.evaluate(REFUSAL_NODES);
    for (const n of now) {
      if (!n.shown || !n.text) continue;
      const was = seen.get(n.key);
      if (was === n.text) continue;             // unchanged and already visible before: not the refusal
      // a node that was hidden before, or whose text changed, is news
      const delta = was ? n.text.split(' · ').filter((t) => !was.includes(t)).join(' · ') : n.text;
      if (delta) found.set(n.key, delta);
    }
  }
  return { text: [...found.values()].join(' | '), nodes: [...found.keys()] };
}

// Reuses the flows already proven reachable by prove_double_fire.mjs, minus one required field.
const FLOWS = {
  // pm-scheduler's EDIT modal (V3). Supervisor-only, pre-filled from currentAsset, and it carries a real
  // dedicated error element (#pm-edit-error, role=alert aria-live=assertive) plus one genuinely required
  // field - saveEditPMAsset() refuses an empty name before it touches the network.
  // PRE-FILLED means the omitted field must be CLEARED, not merely left unfilled: openEditPMAsset() copies
  // currentAsset.asset_name in, so "don't type a name" is not the same as "the name is missing".
  'pm-scheduler-edit': { page: 'pm-scheduler',
    openSteps: [
      { eval: "(() => { const c = document.querySelector('.asset-card'); if (!c) throw new Error('no .asset-card rendered'); c.click(); })()" },
      { eval: "(() => { if (typeof currentAsset === 'undefined' || !currentAsset) throw new Error('no asset opened'); openEditPMAsset(); const m = document.getElementById('pm-edit-modal'); if (getComputedStyle(m).display === 'none') throw new Error('the edit modal did not open - HIVE_ROLE may not be supervisor'); })()" },
      { eval: "(() => { const n = document.getElementById('pm-edit-name'); n.value = ''; n.dispatchEvent(new Event('input', { bubbles: true })); })()" },
    ],
    fill: { '#pm-edit-tag': 'WH-WTF-TAG', '#pm-edit-location': 'Probe Bay 7' },
    omit: '#pm-edit-name',
    omitValue: 'Recovered Asset Name',
    // MEASURED: with these two hung, the schedule rendered 0 asset cards while scopeItems held 144. Both are
    // read-only compliance RPCs; the asset UPDATE this oracle tests stays hung.
    letThrough: ['rpc/get_pm_compliance_smrp', 'rpc/get_pm_ontime_delivery'],
    submit: '#pm-edit-save-btn',
  },
  // hive's INTENT CAPTURE (V3). It is already open at load - the first-run modal - so there is no opener to
  // click. Its only inputs are radios in one group, so there is no free text a refusal could destroy: the
  // preservation half of this oracle has no subject here, and the row records that rather than claiming a
  // preservation it never tested. The omission is therefore the DEFAULT state (nothing selected), and the
  // recovery is a click on one radio, not a fill.
  // report-sender's CONTACTS sheet (V2). The send sheet (V3) reuses the same #sheet-overlay, so the views are
  // told apart by which form is inside it. saveContact() refuses an empty name before touching the network.
  'report-sender-contacts': { page: 'report-sender',
    openSteps: [{ click: '#add-contact-btn' }],
    fill: { '#contact-email': 'wh.probe@example.com' },
    omit: '#contact-name',
    omitValue: 'WH Recovered Contact',
    submit: '#save-contact-btn',
  },
  // inventory's USE sheet (V3). NOTHING HERE CAN BE LEFT MISSING: #use-qty ships value="1" in markup and is
  // re-set to '1' every time the sheet opens, so "don't fill it" leaves a valid quantity and the save is
  // right to succeed — the first run of this flow called that a missing-required-field defect, which was my
  // framing, not the page's fault. The mistake a person actually makes on this sheet is asking for MORE THAN
  // IS ON THE SHELF, and that is the stock-conservation invariant: an over-draw must be refused, the sheet
  // must say what is available, and correcting the number alone must complete the draw.
  'inventory-use': { page: 'inventory',
    openSteps: [{ eval: "(async () => { const t0 = Date.now(); while (Date.now() - t0 < 9000) { "
      + "const b = [...document.querySelectorAll('button')].find((e) => "
      + "((e.textContent || '').trim().toLowerCase().startsWith('use')) && e.offsetParent !== null); "
      + "if (b) { b.click(); return; } await new Promise((r) => setTimeout(r, 250)); } "
      + "throw new Error('no visible Use button appeared within 9s'); })()" },
      { eval: "(() => { const q = document.getElementById('use-qty'); if (!q) throw new Error('#use-qty not present'); "
        + "q.value = '9999'; q.dispatchEvent(new Event('input', { bubbles: true })); "
        + "q.dispatchEvent(new Event('change', { bubbles: true })); })()" }],
    fill: {},
    omit: '#use-qty',
    omitValue: '1',
    submit: '#use-submit-btn',
  },
  // dayplanner's WEEK view (V2). Distinct from V1's "+ Schedule" button: here the action starts from a
  // per-slot "Add task on <day> at <hour>" control, so the slot's own date and time are carried into the
  // shared item modal. Both views render into #calendar-wrap, so the reach PROVES the switch took
  // (#logo-view == 'Week') before hunting for a slot - a silently ignored switch would act on the day grid
  // and file the result against the week.
  'dayplanner-week': { page: 'dayplanner',
    openSteps: [{ eval: "(async () => { if (typeof switchView !== 'function') throw new Error('switchView is not defined'); switchView('wilo'); const l = document.getElementById('logo-view'); if (!l || l.textContent.trim() !== 'Week') throw new Error('the week view did not take'); const t0 = Date.now(); while (Date.now() - t0 < 9000) { const b = [...document.querySelectorAll('#calendar-wrap button, #calendar-wrap [role=button]')].find((e) => ((e.getAttribute('aria-label') || e.textContent || '').trim().toLowerCase().startsWith('add task')) && e.offsetParent !== null); if (b) { b.click(); return; } await new Promise((r) => setTimeout(r, 250)); } throw new Error('no visible Add-task slot button appeared in the week grid within 9s'); })()" }],
    fill: { '#m-notes': 'notes typed before the refusal' },
    omit: '#m-title',
    omitValue: 'recovered week title',
    submit: 'button:has-text("Save")',
  },
  // community's THREAD OVERLAY (V2) - the post with its replies and reactions, distinct from the composer
  // (V3) graded separately. Reached through a post's own "Open thread and reply" control, then PROVEN open
  // before anything is measured, because a silently missed click would grade the feed and file it against
  // the thread.
  'community-thread': { page: 'community',
    openSteps: [{ eval: "(async () => { const t0 = Date.now(); while (Date.now() - t0 < 9000) { const b = [...document.querySelectorAll('button, [role=button]')].find((e) => (e.getAttribute('aria-label') || '').toLowerCase().indexOf('open thread') === 0 && e.offsetParent !== null); if (b) { b.click(); await new Promise((r) => setTimeout(r, 900)); const o = document.getElementById('thread-overlay'); if (!o || getComputedStyle(o).display === 'none') throw new Error('the thread overlay did not open'); return; } await new Promise((r) => setTimeout(r, 250)); } throw new Error('no Open-thread control appeared within 9s'); })()" }],
    fill: {},
    omit: '#reply-content',
    omitValue: 'recovered reply text',
    submit: '#btn-submit-reply',
  },
  // project-manager's CHANGE ORDER (V3) - a financial + approval write, and the one form on this page that
  // must state its effect on BOTH budget and schedule (it carries #co-cost in PHP and #co-days). Reached
  // through the detail view's own "+ Raise change order" control, with both the detail and the dialog PROVEN
  // open before anything is measured.
  'project-manager-co': { page: 'project-manager',
    openSteps: [{ eval: "(async () => { const wait = (ms) => new Promise((r) => setTimeout(r, ms)); const until = async (fn, ms) => { const t = Date.now();   while (Date.now() - t < ms) { const v = fn(); if (v) return v; await wait(200); } return null; }; const card = await until(() => document.querySelector('.pcard'), 9000); if (!card) throw new Error('no .pcard appeared within 9s'); card.click(); const dv = await until(() => { const d = document.getElementById('detail-view');   return d && getComputedStyle(d).display !== 'none' ? d : null; }, 9000); if (!dv) throw new Error('the project detail did not open'); const raise = await until(() => [...document.querySelectorAll('button')].find((e) => /raise change order/i.test((e.textContent || '')) && e.offsetParent !== null), 9000); if (!raise) { if (typeof openNewCO !== 'function') throw new Error('no Raise-change-order control and openNewCO is undefined'); openNewCO(); } else raise.click(); const m = await until(() => { const x = document.getElementById('modal-co');   return x && getComputedStyle(x).display !== 'none' ? x : null; }, 9000); if (!m) throw new Error('#modal-co did not open'); })()" }],
    fill: { '#co-scope': 'probe scope change: add two anchor restraints' },
    omit: '#co-title',
    omitValue: 'recovered change order title',
    submit: '#form-co button[type=submit]',
  },
  // index's SIGN-IN modal (V3). Opened by REVEALING #signin-modal rather than by pressing the page's
  // openSignIn(), and that is a deliberate, stated compromise: openSignIn() checks for a stored worker name
  // first and toggles the USER MENU instead when one exists, so on a signed-in context - which is what these
  // provers establish - the real opener never reaches this dialog. What is being graded here is a CLIENT-SIDE
  // validation branch that runs before any network call, so revealing the dialog measures exactly the same
  // code path a signed-out visitor would hit. It does NOT prove the opener works for an anon visitor; that is
  // a different claim and is not made.
  'index-signin': { page: 'index',
    openSteps: [{ eval: "(() => { const m = document.getElementById('signin-modal'); if (!m) throw new Error('#signin-modal is not in the DOM'); m.classList.remove('hidden'); if (m.classList.contains('hidden')) throw new Error('the sign-in modal stayed hidden'); })()" }],
    fill: { '#si-username': 'wh.probe.user' },
    omit: '#si-password',
    omitValue: 'probe-password',
    submit: '#panel-signin button[type=submit]',
  },
  'hive-intent': { page: 'hive',
    openSteps: [
      // POLLED, not asserted at one instant: this modal is raised after the board's own loads settle, and at
      // this prover's 4.2s mark it was not up yet — which read as "already answered this session" when the
      // truth was that I looked too early. A reach that asserts at a fixed moment measures my timing.
      { eval: "(async () => { const t0 = Date.now(); while (Date.now() - t0 < 9000) { const m = document.getElementById('intent-capture'); if (m && getComputedStyle(m).display !== 'none' && document.querySelectorAll('input[name=\"intent-primary\"]').length) return; await new Promise((r) => setTimeout(r, 250)); } const m2 = document.getElementById('intent-capture'); throw new Error(m2 ? ('the intent modal never opened within 9s (display=' + getComputedStyle(m2).display + ') — it may already have been answered') : '#intent-capture is not in the DOM'); })()" },
      { eval: "(() => { document.querySelectorAll('input[name=\"intent-primary\"]').forEach((r) => { r.checked = false; }); })()" },
    ],
    fill: {},
    omitClick: 'input[name=\"intent-primary\"]',
    // MEASURED: with this hung, the board never finished loading and the intent modal never opened at all
    // (display stayed 'none' for 9s). It is the board's own read; the hives UPDATE this oracle tests stays hung.
    letThrough: ['rpc/get_hive_board_dashboard'],
    submit: '#intent-save',
  },
  inventory: {
    open: 'button:has-text("Add Part")',
    fill: { '#f-part-number': 'WH-WTF-PROBE', '#f-qty': '1' },
    omit: '#f-part-name',
    omitValue: 'recovered part name',
    submit: '#part-submit-btn',
  },
  logbook: {
    open: 'button:has-text("Register Asset")',
    fill: { '#a-asset-id': 'WH-WTF-PROBE' },
    omit: '#a-name',
    omitValue: 'recovered asset name',
    submit: '#asset-submit-btn',
  },
  dayplanner: {
    open: 'button:has-text("+ Schedule")',
    fill: { '#m-notes': 'notes typed before the refusal' },
    omit: '#m-title',
    omitValue: 'recovered title',
    submit: 'button:has-text("Save")',
  },
  community: {
    open: '#fab-post',
    // The category select is left at its default (General, a deliberate safe default), so CONTENT is the
    // only thing missing — the omitted field under test must be the sole omission or the run measures a
    // different refusal than the one it names.
    fill: {},
    omit: '#post-content',
    omitValue: 'recovered post content',
    submit: '#btn-submit-post',
  },
  'asset-hub': {
    // Three gates, as the double-fire flow established: in-page click for the detail (a Playwright click
    // is intercepted), the opt-in Reliability Workbench (#reliability-card ships display:none), then FMEA.
    openSteps: [
      { eval: "document.querySelector('.asset-card') && document.querySelector('.asset-card').click()" },
      { click: '#asset-view-toggle' },
      { click: '[data-tab="fmea"]' },
      { click: '#fmea-add-btn' },
    ],
    fill: { '#fmea-function': 'wtf probe function' },
    omit: '#fmea-failure-mode',
    omitValue: 'recovered failure mode',
    submit: '#fmea-save',
  },
  // ★A DISABLED SUBMIT IS PREVENTION, NOT REFUSAL — a THIRD outcome this oracle has to name.
  // report-sender and assistant keep their submit disabled until the form is valid, so pressing it does
  // nothing at all: there is no refusal to recover from, and equally nothing was ever destroyed. That is
  // arguably the better design (it cannot be submitted wrong), but it only satisfies "corrected without
  // starting over" if the person can tell WHAT is missing — otherwise they are holding an intact form and
  // a dead button, which is its own kind of stuck. So this is measured and reported as `prevented`, and
  // graded on whether a hint names the missing requirement.
  'report-sender': {
    open: 'button:has-text("PM Overdue")',
    fill: {},
    omit: '#email-input',
    omitValue: 'probe@example.com',
    submit: '#send-btn',
    expectPrevented: true,
  },
  assistant: {
    open: '#tab-chat',
    fill: {},
    omit: '#chat-input',
    omitValue: 'recovered question',
    submit: '#send-btn',
    expectPrevented: true,
  },
  // The CAPTURE modal, with the IMPACT deliberately omitted — the field whose refusal was invisible until
  // showToast was fixed this session (it was being handed an emoji where a duration belongs, so nine
  // validation messages rendered for 0ms). This row therefore tests the repair as well as the oracle: the
  // refusal must now be readable, the typed narrative must survive it, and supplying the one missing
  // choice must let the save proceed.
  'logbook-capture': {
    page: 'logbook',
    openSteps: [
      { eval: "document.getElementById('asset-picker-btn') && document.getElementById('asset-picker-btn').click()" },
      { eval: "(() => { const m = document.getElementById('asset-picker-modal'); if (!m) return; const r = [...m.querySelectorAll('button,li,[role=option],div[data-asset-id]')].find(e => { const s = getComputedStyle(e); return s.display !== 'none' && e.getBoundingClientRect().height > 0 && (e.innerText || '').trim().length > 2; }); if (r) r.click(); })()" },
      { eval: "(() => { const b = [...document.querySelectorAll('button')].find(e => /what happened/i.test(e.innerText || '')); if (b) b.click(); })()" },
    ],
    // ★#f-root-cause IS A <select>, NOT A TEXT INPUT — and putting it in `fill` produced a FABRICATED
    // FAILURE: page.fill never set it, the read-back returned '', and the probe reported that "the refusal
    // DESTROYED what had already been typed" on a page that had preserved everything it was actually given.
    // #f-problem, the one genuinely typed field, came back intact. A field the probe never filled is not a
    // field the page erased — checking the element TYPE before claiming data loss is the whole difference
    // between a defect and a slander.
    fill: { '#f-problem': 'probe: drive tripped on overload' },
    selects: { '#f-maint-type': 1, '#f-category': 1, '#f-wo-state': 1, '#f-root-cause': 1 },
    afterFill: [
      { eval: "(() => { const b = [...document.querySelectorAll('button')].find(e => /what did you do/i.test(e.innerText || '')); if (b) b.click(); })()" },
      { eval: "(() => { const e = document.getElementById('f-action'); if (e) { e.value = 'probe: retightened the terminal'; e.dispatchEvent(new Event('input', { bubbles: true })); } })()" },
    ],
    // The omission under test: the impact is chosen by a BUTTON, not typed — a hidden input behind
    // .consequence-btn — so 'omit' is satisfied by simply not clicking it.
    omitClick: '.consequence-btn[data-value]',
    omit: null,
    submit: '#save-entry-btn',
  },
  'pm-scheduler': {
    open: '#tab-add',
    // CATEGORY IS ALSO REQUIRED, and leaving it unset is why the first run could not confirm the
    // recovery: step 1 gates on name AND category, so supplying only the name still left the wizard
    // blocked and the probe honestly reported that it could not verify the path. The omitted field under
    // test must be the ONLY thing missing, or the test is measuring a different refusal than it claims.
    fill: { '#w-tag': 'WH-WTF-PM', '#w-location': 'Probe Bay' },
    selects: { '#w-category': 1 },
    omit: '#w-name',
    omitValue: 'recovered asset name',
    submit: null,             // step 1 advances rather than submits; the refusal is the block itself
    advanceOnly: true,
  },
};

if (args.includes('--selftest')) {
  const b = await chromium.launch();
  const c = await b.newContext({ viewport: { width: 390, height: 844 } });
  const pg = await c.newPage();
  await pg.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  let fail = 0;
  // KEEPS: refuses, says why, and leaves the typing alone.  WIPES: refuses and clears the form —
  // the defect. Both must be told apart, or a detector that always says "preserved" blesses the wipe.
  await pg.evaluate(() => {
    const mk = (id, wipes, top) => {
      const wrap = document.createElement('div');
      wrap.style.cssText = `position:fixed;top:${top}px;left:0;z-index:99999;background:#111;padding:8px`;
      wrap.innerHTML = `<input id="${id}-a" value=""><input id="${id}-b" value="">`
        + `<div id="${id}-err" style="display:none">Name is required.</div>`
        + `<button id="${id}-go">Save</button>`;
      document.body.appendChild(wrap);
      wrap.querySelector(`#${id}-go`).addEventListener('click', () => {
        if (!wrap.querySelector(`#${id}-b`).value) {
          wrap.querySelector(`#${id}-err`).style.display = 'block';
          if (wipes) wrap.querySelector(`#${id}-a`).value = '';   // destroys what they typed
        }
      });
    };
    mk('wh-keep', false, 0); mk('wh-wipe', true, 120);
  });
  for (const [id, wipes] of [['wh-keep', false], ['wh-wipe', true]]) {
    await pg.fill(`#${id}-a`, 'typed by the person');
    await pg.click(`#${id}-go`, { force: true });
    await pg.waitForTimeout(200);
    const kept = await pg.evaluate((x) => document.querySelector(`#${x}-a`).value, id);
    const said = (await pg.evaluate(REFUSAL_NODES)).filter((n) => n.shown && n.text)
      .map((n) => n.text).join(' | ');
    const preserved = kept === 'typed by the person';
    if (!wipes && !(preserved && said)) { console.log(`  FAIL — a form that PRESERVES was misread (kept=${preserved}, said="${said}")`); fail++; }
    else if (wipes && preserved) { console.log('  FAIL — a form that WIPED the entry was reported as preserving'); fail++; }
    else if (!wipes) console.log(`  ok — preserved entry + legible refusal seen ("${said.slice(0, 40)}")`);
    else console.log('  ok — the WIPING form was CAUGHT losing what was typed');
  }
  await b.close();
  console.log(fail ? `\n  SELFTEST FAILED (${fail})`
    : '\n  SELFTEST PASSED — preserves-and-explains passes, wipes-on-refusal is caught');
  process.exit(fail ? 1 : 0);
}

const browser = await chromium.launch();
const report = { ran: new Date().toISOString(), origin: ORIGIN, pages: {} };
for (const p of (ONE ? [ONE] : Object.keys(FLOWS))) {
  const flow = FLOWS[p];
  const rec = { page: p };
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  await ctx.addInitScript(HANG_WRITES, (FLOWS[p] && FLOWS[p].letThrough) || []);
  const page = await ctx.newPage();
  try {
    await page.goto(`${ORIGIN}/${(FLOWS[p] && FLOWS[p].page) || p}.html`,
                    { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(4200);
    if (flow.openSteps) {
      for (const st of flow.openSteps) {
        // A swallowed setup error reads downstream as a page defect. It must not be swallowed.
        if (st.eval) await page.evaluate(st.eval).catch((e) => {
          throw new Error('setup step failed: ' + String(e && e.message || e).slice(0, 120));
        });
        else await page.click(st.click, { timeout: 6000 }).catch(() => {});
        await page.waitForTimeout(700);
      }
    } else {
      await page.click(flow.open, { timeout: 6000 }).catch(() => {});
      await page.waitForTimeout(800);
    }
    const sels = Object.keys(flow.fill);
    for (const [sel, val] of Object.entries(flow.fill)) {
      await page.fill(sel, val, { timeout: 6000 }).catch(() => {});
    }
    // ★VERIFY EVERY FILL LANDED BEFORE THIS ORACLE MAY CLAIM DATA LOSS. Without this the prover accused
    // logbook of DESTROYING a person's typed entry, when the truth was that I had listed a <select> in the
    // fill map: page.fill never set it, the read-back was empty, and "empty after the refusal" was
    // indistinguishable from "erased by the refusal". A field the probe never filled is not a field the
    // page erased — and on a page whose write feeds eleven consumers, that difference is a defect versus a
    // slander. Any unset field now makes the row UNGRADED with the element type named, so the flow gets
    // fixed instead of the product getting blamed.
    const fillCheck = await page.evaluate((entries) => entries.map(([sel, want]) => {
      const e = document.querySelector(sel);
      if (!e) return { sel, ok: false, why: 'selector matched nothing' };
      const tag = e.tagName.toLowerCase();
      const got = e.value === undefined ? (e.textContent || '').trim() : e.value;
      if (got === want) return { sel, ok: true };
      return { sel, ok: false, why: `<${tag}${e.type ? ' type=' + e.type : ''}> holds ${JSON.stringify(String(got).slice(0, 30))}`
        + (tag === 'select' ? ' — a <select> cannot be filled; declare it under `selects`' : '') };
    }), Object.entries(flow.fill));
    const unset = fillCheck.filter((x) => !x.ok);
    if (unset.length) {
      rec.status = 'UNGRADED';
      rec.fillCheck = unset;
      rec.why = 'the probe could not populate ' + unset.map((x) => `${x.sel} (${x.why})`).join('; ')
        + ' — so an empty read-back after the refusal would be MY omission, not the page erasing anything. '
        + 'Refusing to grade rather than risk a false data-loss finding.';
      report.pages[p] = rec;
      console.log(`  ${p.padEnd(15)} ${'UNGRADED'.padEnd(9)} ${rec.why}`.slice(0, 165));
      await ctx.close();
      continue;
    }
    for (const [sel, idx] of Object.entries(flow.selects || {})) {
      await page.evaluate(({ s: sl, i }) => {
        const e = document.querySelector(sl);
        if (e && e.options && e.options.length > i) {
          e.selectedIndex = i; e.dispatchEvent(new Event('change', { bubbles: true }));
        }
      }, { s: sel, i: idx }).catch(() => {});
    }
    // ★THE REFUSAL MUST BE A DIFFERENCE, NOT A STRING THAT WAS ALWAYS THERE. Reading the live regions
    // once AFTER the submit credited the persistent SOURCE CHIP ("Live - refreshed on load - Based on
    // your inventory & stock movements"), which is mounted with aria-live and says the same thing before
    // anyone touches the form. So the surface is read BEFORE the submit and the refusal must be text
    // that APPEARED. This is the same rule the failure-injection oracle already enforces: if the healthy
    // page said it too, it proves nothing.
    const beforeNodes = await page.evaluate(REFUSAL_NODES);
    const saidBefore = beforeNodes.filter((n) => n.shown && n.text).map((n) => n.text).join(' | ');
    // afterFill runs LAST: the step-2 -> step-3 advance must happen after step 2's selects are set, or the
    // wizard refuses to move and the probe measures a different refusal than the one it names.
    for (const st of (flow.afterFill || [])) {
      if (st.eval) await page.evaluate(st.eval).catch(() => {});
      await page.waitForTimeout(700);
    }
    await page.evaluate(() => { window.__whW.count = 0; });
    // Submit (or advance) with the required field MISSING.
    if (flow.advanceOnly) {
      await page.evaluate(() => {
        const b = [...document.querySelectorAll('button')]
          .find((e) => /^next/i.test((e.innerText || '').trim()) && !e.disabled && e.offsetParent !== null);
        if (b) b.click();
      });
    } else {
      const occ = await occludedBy(page, flow.submit);
      if (occ) {
        rec.status = 'UNGRADED';
        rec.why = `cannot press ${flow.submit}: ${occ.why}. Refusing to grade — a control I could not reach `
          + 'tells me nothing about how this page refuses, and pressing through it would measure whatever '
          + 'is on top instead.';
        rec.occlusion = occ;
        report.pages[p] = rec;
        console.log(`  ${p.padEnd(15)} ${'UNGRADED'.padEnd(9)} ${rec.why}`.slice(0, 165));
        await ctx.close();
        continue;
      }
      await page.click(flow.submit, { force: true, timeout: 6000 }).catch(() => {});
    }
    // Sampled ACROSS the refusal's life (250/600/1200/2000ms), not read once at 900ms: a toast that lives
    // 3s is still a moving target, and the earlier single read scored hive's clear "Pick one to save, or tap
    // Later." as silence.
    // ★THE BROWSER'S OWN REFUSAL IS STILL A REFUSAL. #co-title and #co-scope carry the HTML `required`
    // attribute, so native constraint validation blocks the submit BEFORE the handler runs: showToast never
    // fires, and the message the person sees is a native bubble that lives outside the DOM entirely. This
    // prover read that as "the refusal said NOTHING a person could read" on a form that names the field and
    // the reason. Native validity is measurable even though its bubble is not, so it is measured.
    const native = await page.evaluate((omitSel) => {
      const el = omitSel ? document.querySelector(omitSel) : null;
      const form = el ? el.closest('form') : null;
      return {
        omittedInvalid: !!(el && el.willValidate && !el.checkValidity()),
        omittedRequired: !!(el && (el.required || el.getAttribute('aria-required') === 'true')),
        formInvalid: !!(form && !form.checkValidity()),
        message: (el && el.validationMessage) || null,
      };
    }, flow.omit || null);
    rec.nativeValidation = native;
    const diff = await refusalDiff(page, beforeNodes);
    const said = diff.text;
    rec.refusalNodes = diff.nodes;
    const wrote = await page.evaluate(() => window.__whW.count);
    const submitDisabled = flow.submit ? await isDisabled(page, flow.submit) : false;
    rec.submitDisabled = submitDisabled;
    rec.refusalBefore = saidBefore.slice(0, 160);
    const kept = await page.evaluate(READ_FIELDS, sels);
    const preserved = sels.every((s) => (kept[s] || '') === flow.fill[s]);
    rec.wroteOnIncomplete = wrote; rec.refusalText = said; rec.kept = kept;
    if (submitDisabled && wrote === 0) {
      // Prevention. Nothing was submitted and nothing was lost; the question is whether the surface says
      // what is still needed. Supplying the omitted value must then ENABLE the control.
      const hint = said;
      await page.fill(flow.omit, flow.omitValue, { timeout: 6000 }).catch(() => {});
      await page.waitForTimeout(500);
      const nowEnabled = !(await isDisabled(page, flow.submit));
      rec.enabledAfterFix = nowEnabled;
      rec.status = nowEnabled ? 'PASS' : 'UNGRADED';
      rec.why = nowEnabled
        ? 'the submit is PREVENTED rather than refused - held disabled while the form is incomplete, so '
          + 'nothing could be submitted wrong and nothing was ever destroyed - and supplying the single '
          + 'missing value ENABLED it, which is a one-field correction with no re-entry'
          + (hint ? ` (a hint was also shown: "${hint.slice(0, 60)}")` : ' (no hint names the missing field, '
            + 'which is a legibility gap rather than a data-loss one)')
        : 'the submit stayed disabled even after the missing field was supplied, so the recovery path '
          + 'could not be confirmed from here';
    } else if (wrote > 0) {
      rec.status = 'UNGRADED';
      rec.why = 'the form was ACCEPTED with the required field missing, so there was no refusal to '
        + 'recover from — that is a missing-required-field finding for a different row, not this one';
    } else if (!preserved) {
      rec.status = 'FAIL';
      rec.why = 'the refusal DESTROYED what had already been typed — the person must start over, which '
        + 'is precisely what this oracle forbids';
    } else if (!said && native.omittedInvalid && native.formInvalid) {
      // The browser refused it, and said so in a bubble that is outside the DOM. That is a legible refusal
      // to the person even though no element carries the text — and it is anchored to the exact field, which
      // is more precise than most in-page messages. Recorded as its own outcome so the row can say WHICH
      // mechanism refused rather than implying the page authored a message it did not.
      rec.status = 'PASS';
      rec.refusalMechanism = 'native constraint validation';
      rec.why = 'the refusal preserved every field already typed and came from NATIVE constraint validation '
        + `on ${flow.omit} (validationMessage: ${JSON.stringify(native.message || '')}) — the browser blocked `
        + 'the submit before the handler ran, so no in-page message exists to read, and nothing was written';
    } else if (!said) {
      rec.status = 'FAIL';
      rec.why = 'the entry survived, but the refusal said NOTHING a person could read — they are left '
        + 'with an intact form and no idea what to change, which is still starting over by another name'
        + (native.omittedRequired ? ' (note: the omitted field IS marked required, but native validation did '
          + 'not block the submit — check whether the form bypasses it)' : '');
    } else {
      // Now prove the correction is a ONE-FIELD fix: supply the omitted value and submit again.
      if (flow.omitClick) {
        // The recovery here is a CLICK, not a keystroke: the missing value is set by a button.
        await page.evaluate((sel) => { const b = document.querySelector(sel); if (b) b.click(); }, flow.omitClick)
          .catch(() => {});
      } else if (flow.omit) {
        await page.fill(flow.omit, flow.omitValue, { timeout: 6000 }).catch(() => {});
      }
      await page.waitForTimeout(400);
      if (flow.advanceOnly) {
        await page.evaluate(() => {
          const b = [...document.querySelectorAll('button')]
            .find((e) => /^next/i.test((e.innerText || '').trim()) && !e.disabled && e.offsetParent !== null);
          if (b) b.click();
        });
      } else {
        await page.click(flow.submit, { force: true, timeout: 6000 }).catch(() => {});
      }
      await page.waitForTimeout(1000);
      const after = await page.evaluate(() => window.__whW.count);
      const advanced = flow.advanceOnly
        ? await page.evaluate(() => {
          const v = (e) => { if (!e) return false; const s = getComputedStyle(e);
            const b = e.getBoundingClientRect(); return s.display !== 'none' && b.height > 0; };
          return !v(document.getElementById('step-1'));
        })
        : after > 0;
      rec.recovered = advanced;
      rec.status = advanced ? 'PASS' : 'UNGRADED';
      rec.why = advanced
        ? `the refusal preserved every field already typed and said why ("${said.slice(0, 70)}"), and `
          + 'supplying the single missing value was enough to proceed — a one-field correction, not a re-entry'
        : 'the entry survived and the refusal was legible, but supplying the missing field did not let the '
          + 'form proceed, so the recovery path could not be confirmed from here';
    }
  } catch (e) {
    rec.status = 'UNGRADED'; rec.why = 'probe error: ' + String(e).slice(0, 90);
  }
  report.pages[p] = rec;
  console.log(`  ${p.padEnd(15)} ${String(rec.status).padEnd(9)} ${rec.why || ''}`.slice(0, 165));
  await ctx.close();
}
writeFileSync('wrong_then_fix_report.json', JSON.stringify(report, null, 1));
const v = Object.values(report.pages);
console.log(`\n  wrote wrong_then_fix_report.json — ${v.filter((x) => x.status === 'PASS').length} pass, `
  + `${v.filter((x) => x.status === 'FAIL').length} fail, ${v.filter((x) => x.status === 'UNGRADED').length} ungraded`);
console.log('  NO WRITE REACHED THE DATABASE: the refusal path writes nothing, and the recovery write was held.');
await browser.close();
