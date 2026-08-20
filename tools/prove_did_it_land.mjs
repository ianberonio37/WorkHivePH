// prove_did_it_land.mjs — CO `did_it_land`: "after a slow action the person can tell whether it landed,
// without guessing."
//
// THE ORACLE IS ABOUT THE MOMENT AFTER, NOT THE MOMENT DURING. `prove_double_fire.mjs` holds a write open
// forever and asks whether the control refuses a second press — that is the IN-FLIGHT question. This asks
// the one that comes next: the request eventually finishes, and the person is left looking at a screen.
// Can they tell what happened? A page that shows a spinner, resolves silently, and leaves the form exactly
// as it was has answered nothing — the person's only options are to guess or to press again, which is how
// a duplicate gets created by someone being careful.
//
// SO THE WRITE IS DELAYED, NOT HUNG. fetch is replaced in an addInitScript (before supabase-js constructs
// its client, above the service worker) and every mutating request to /rest/v1/, /rpc/ or /functions/ is
// held for a fixed delay and then RESOLVED WITH A SYNTHETIC SUCCESS. Nothing reaches the database: the
// real request is never issued, and the response is manufactured in the page.
//
// ★WHY A SYNTHETIC SUCCESS IS HONEST HERE, AND WHERE IT WOULD NOT BE.
// This oracle asks what the SURFACE tells a person after a completed action. It does not ask whether the
// server accepted the row — that is CF's effect_in_db, proven elsewhere against the real database. So
// standing in for the server is legitimate for this question and only this one. The response is shaped
// the way PostgREST actually answers (201 with a representation array for an insert, 200 otherwise), so
// the page's own success path runs rather than an error path pretending to be one.
//
// THE DELAY IS THE WHOLE POINT. "After a SLOW action" — a write that completes in 40ms locally never
// creates the interval where a person is left wondering, so a page could pass this oracle by being fast
// rather than by being clear. Holding it 2.5s manufactures the wait that makes the question real.
//
// WHAT COUNTS AS TELLING THEM. Measured as a DIFFERENCE across the completion, not as a string match on a
// page that might have said the words all along: the surface is read immediately before the response
// lands and again after, and something a person can perceive must CHANGE — a toast or live region
// appears, the control returns from its busy state, the dialog closes, or the rendered content changes.
// A page identical before and after has told them nothing.
//
// Usage:
//   node tools/prove_did_it_land.mjs                # every page with a flow
//   node tools/prove_did_it_land.mjs --page logbook
//   node tools/prove_did_it_land.mjs --selftest     # teeth, both directions, no product involved
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const DELAY_MS = 2500;

const DELAY_WRITES = (delayMs) => {
  window.__whLand = { count: 0, settled: 0, edge: 0 };
  const of = window.fetch;
  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    const mutating = ['POST', 'PATCH', 'PUT', 'DELETE'].includes(method);
    if (mutating && /\/rest\/v1\/|\/rpc\/|\/functions\/v1\//.test(url)) {
      window.__whLand.count++;
      // Record WHICH transport the action used. It decides whether a synthetic answer is faithful.
      if (/\/functions\/v1\//.test(url)) window.__whLand.edge++;
      // Shaped like the REAL answer for whichever transport this is, so the page runs its SUCCESS path
      // rather than an error path wearing a success costume.
      //   PostgREST  -> 201 + a representation array (fixed, documented shape)
      //   ai-gateway -> the envelope assistant.html actually reads: { ok, data:{ answer } }, checked at
      //                 :1022 (`if (!r || r.error || !r.data) return null`) and :1055 (`orchData.answer`)
      // A generic echo is NOT an edge function's answer, and using one had the page render nothing while
      // I very nearly recorded that silence as the product failing to report an outcome.
      let payload = [];
      let status = method === 'POST' ? 201 : 200;
      // ★A GENERATOR RPC RETURNS A SCALAR, NOT THE REQUEST BODY. Echoing the body back for
      // rpc/generate_change_order_number made the page render "[object Object] submitted for approval" —
      // my stub's text, graded as the product's sentence. A synthetic response has to be shaped like the
      // real service or the reading is about the stub.
      // ★THE GRADER RETURNS {score, passed}, NOT THE REQUEST. Echoing the body back left graded.score and
      // graded.passed undefined, so skillmatrix took its FAIL branch and rendered "Score: undefined / 10" -
      // my stub's verdict, graded as the page's. The walk answers using the page's OWN answer key, so a
      // faithful grader would return a full score; that is what is synthesized here. This stub deliberately
      // says nothing about whether the real grader scores correctly - that is a different claim, proven
      // server-side, and must not be smuggled in through a UI walk.
      // ★THE WEIBULL FITTER RETURNS A FIT, NOT THE REQUEST. asset-hub branches on
      // data.failure_pattern === 'insufficient_data' and claims a downstream ripple ONLY when the fit is
      // defensible, so an echoed request body would push the page down its insufficient-data path and grade
      // the consolation sentence instead of the real one. Synthesized as a defensible wear-out fit: beta > 1
      // is exactly the case whose confirmation names the risk-score ripple.
      // The shift planner's contract is thin and explicit: the page treats any data.error as failure and
      // otherwise takes the success path, so a faithful synthetic answer is simply a payload without one.
      if (/\/functions\/v1\/shift-planner-orchestrator/.test(url)) {
        payload = { ok: true, regenerated: true }; status = 200;
      } else if (/\/functions\/v1\/weibull-fitter/.test(url)) {
        payload = { failure_pattern: 'wear_out', beta: 2.1, eta: 420, r_squared: 0.94, n_failures: 9 };
        status = 200;
      } else if (/\/rpc\/grade_skill_exam/.test(url)) {
        let n = 10;
        try { const body = JSON.parse(init.body); if (Array.isArray(body.p_answers)) n = body.p_answers.length; } catch (_) { n = 10; }
        payload = { score: n, passed: n >= 7 }; status = 200;
      } else if (/\/rpc\/generate_/.test(url)) {
        payload = 'WH-PROBE-0001'; status = 200;
      } else if (/\/functions\/v1\/(ai-gateway|ai-orchestrator)/.test(url)) {
        payload = { ok: true, data: { answer: 'Probe reply: this is a stubbed gateway answer.' } };
        status = 200;
      } else {
        try { payload = init && init.body ? [JSON.parse(init.body)].flat() : []; } catch (_) { payload = []; }
      }
      return new Promise((resolve) => setTimeout(() => {
        window.__whLand.settled++;
        resolve(new Response(JSON.stringify(payload), {
          status, headers: { 'Content-Type': 'application/json' },
        }));
      }, delayMs));
    }
    return of.apply(this, arguments);
  };
};

// A perceivable snapshot of the surface. Deliberately coarse: this asks whether a PERSON could notice a
// change, not whether the DOM differs by a byte.
const SNAP = () => {
  const vis = (e) => {
    if (!e) return false;
    const s = getComputedStyle(e); const b = e.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05
      && b.width > 0 && b.height > 0;
  };
  // ★KEYED PER NODE, not one joined string truncated at 200 chars — and stamped, because index-based keys
  // shift the moment a toast appears. A joined-and-cut read let a permanently-visible SOURCE CHIP
  // ("Live · refreshed on load · Based on your inventory & stock…") stand in for the confirmation: the chip
  // re-renders when the write completes, so "the text changed" was true and told the person nothing about
  // whether their stock draw landed. This platform's chips are legitimately role=status + aria-live, so the
  // only property that separates an announcement from churn is that the announcement WAS NOT THERE BEFORE.
  window.__whlK = window.__whlK || 0;
  const liveNodes = [...document.querySelectorAll(
    '#toast, [id*="toast"], [class*="toast"], [role="status"], [role="alert"], [aria-live]')]
    .filter(vis).map((e) => {
      if (!e.dataset.whlKey) e.dataset.whlKey = 'k' + (++window.__whlK);
      return { key: e.id ? '#' + e.id : e.dataset.whlKey,
               text: (e.textContent || '').trim().slice(0, 200) };
    }).filter((n) => n.text);
  const liveText = liveNodes.map((n) => n.text).join(' | ').slice(0, 200);
  const openDialogs = [...document.querySelectorAll('[role="dialog"], dialog, [class*="modal"]')]
    .filter(vis).length;
  const busy = document.querySelectorAll('[aria-busy="true"]').length
    + [...document.querySelectorAll('button')].filter((b) => b.disabled && vis(b)).length;
  const main = document.querySelector('main') || document.body;
  return {
    liveText,
    liveNodes,
    openDialogs,
    busy,
    contentLen: ((main.innerText || '').replace(/\s+/g, ' ').trim()).length,
  };
};

// ★A WAIT STATE IS NOT A LANDING, AND A SOURCE CHIP IS NOT A MESSAGE. Two texts kept qualifying as "the
// surface confirmed it": assistant's "Thinking…", which says the write is IN FLIGHT — the opposite of landed —
// and pm-scheduler's "Live · refreshed on load · Based on your PM assets…", which is the page's provenance
// chip re-appearing when its panel re-renders. Both are newly visible, so the newly-visible rule alone let
// them through. Excluded by their own wording, harvested from this product's copy rather than invented.
const WAIT_TEXT = /\b(thinking|loading|working|fetching|generating|calculating|saving|sending|please wait)\b|…$/i;
const CHIP_TEXT = /based on your|refreshed on load|^live\s*[·|]|updates automatically|source:/i;
const isRealMessage = (t) => !!t && !WAIT_TEXT.test(t.trim()) && !CHIP_TEXT.test(t.trim());

const DIFF = (a, b) => {
  const reasons = [];
  // A message counts only if it is NEW — a node not visible before this action, or an announcing element.
  // A chip that was on screen all along and merely re-rendered is not the surface telling anyone anything.
  const wasVisible = new Map((a.liveNodes || []).map((n) => [n.key, n.text]));
  const fresh = (b.liveNodes || []).filter((n) => {
    const prev = wasVisible.get(n.key);
    if (prev === undefined) return true;                 // appeared: this is an announcement
    // ...and a TOAST that now says something different is also an announcement. Excluding it outright was
    // too strict and cost logbook its verdict: its #toast element can already be on screen from an earlier
    // step, so "was visible before" is not the same as "said this before". The name is the discriminator —
    // this platform's toasts are id/class-named toast, while its permanently-visible SOURCE CHIPS are
    // role=status + aria-live, which is why role cannot be used here.
    if (/toast|alert/i.test(n.key) && prev !== n.text) return true;
    return false;                                        // a chip that merely re-rendered: churn
  });
  const real = fresh.filter((n) => isRealMessage(n.text));
  if (real.length) reasons.push(`a message appeared: "${real.map((n) => n.text).join(' | ').slice(0, 90)}"`);
  if (b.openDialogs < a.openDialogs) reasons.push('the dialog closed');
  // ★COMING OUT OF BUSY IS NOT AN ANSWER, and crediting it would have passed a page that says nothing.
  // My own self-test caught this: the SILENT fixture — which resolves the write and deliberately reports
  // nothing — was credited purely because its button re-enabled. But a control leaves its busy state on
  // success AND on failure, so it tells a person the action is OVER, never whether it WORKED. That is
  // precisely the guessing this oracle exists to forbid. A dialog CLOSING is different and does count:
  // these forms stay open on error and close on success, so closing carries the outcome.
  if (Math.abs(b.contentLen - a.contentLen) > 12) {
    reasons.push(`the rendered content changed (${a.contentLen} -> ${b.contentLen} chars)`);
  }
  return reasons;
};

if (args.includes('--selftest')) {
  const b = await chromium.launch();
  let fail = 0;
  // TELLS: a control that announces the outcome when the request resolves.
  // SILENT: one that resolves and leaves the surface exactly as it was — the defect this oracle exists for.
  for (const [name, tells] of [['tells', true], ['silent', false]]) {
    const c = await b.newContext({ viewport: { width: 390, height: 844 } });
    await c.addInitScript(DELAY_WRITES, 600);
    const pg = await c.newPage();
    await pg.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await pg.evaluate((doesTell) => {
      const btn = document.createElement('button');
      btn.id = 'wh-land-btn'; btn.textContent = 'Save';
      btn.style.cssText = 'position:fixed;top:0;left:0;width:120px;height:44px;z-index:99999';
      const out = document.createElement('div');
      out.id = 'wh-land-out'; out.setAttribute('role', 'status');
      out.style.cssText = 'position:fixed;top:60px;left:0;z-index:99999';
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        await fetch('/rest/v1/thing', { method: 'POST', body: '{"a":1}' });
        btn.disabled = false;
        if (doesTell) out.textContent = 'Saved — your entry is in.';   // says what happened
        // when !doesTell: resolves and says nothing at all
      });
      document.body.append(btn, out);
    }, tells);
    await pg.click('#wh-land-btn', { force: true });
    await pg.waitForTimeout(150);
    const before = await pg.evaluate(SNAP);
    await pg.waitForTimeout(1200);
    const after = await pg.evaluate(SNAP);
    const reasons = await pg.evaluate(([a, x]) => null, [before, after]) || DIFF(before, after);
    const told = reasons.length > 0;
    if (tells && !told) { console.log('  FAIL — a control that ANNOUNCED the outcome was read as silent'); fail++; }
    else if (!tells && told) { console.log(`  FAIL — a SILENT control was credited (${reasons.join('; ')})`); fail++; }
    else if (tells) console.log(`  ok — the telling control was seen to tell: ${reasons.join('; ')}`);
    else console.log('  ok — the silent control was CAUGHT saying nothing after the write landed');
    await c.close();
  }
  await b.close();
  console.log(fail ? `\n  SELFTEST FAILED (${fail})`
    : '\n  SELFTEST PASSED — a page that announces the outcome passes, one that resolves in silence is caught');
  process.exit(fail ? 1 : 0);
}

// Reuse the flows already proven by prove_double_fire.mjs — same pages, same reachable submits.
// ★SOME CONTROLS ONLY ANSWER AN IN-PAGE CLICK. asset-hub's .asset-card is intercepted for a Playwright click
// while element.click() works, and shift-brain's plan-body controls behave the same - they sit thousands of
// pixels below the fold (publish measured at y=3221 on a 390x844 viewport) and a coordinate click never
// reached their handlers, so a working action read as "produced no mutating request". Declared PER FLOW, not
// globally: a coordinate click is the more faithful gesture where it works, because it is the one that catches
// an occluded or unreachable control.
async function pressCtl(page, sel, via) {
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
  await page.click(sel, { force: true, timeout: 6000 });
}

const FLOWS = {
  'report-sender': { steps: [{ click: 'button:has-text("PM Overdue")' },
                             { fill: '#email-input', value: 'probe@example.com' }],
                     submit: 'button:has-text("Send Reports")' },
  dayplanner: { steps: [{ click: 'button:has-text("+ Schedule")' },
                        { fill: '#m-title', value: 'wh land probe' }],
                submit: 'button:has-text("Save")' },
  logbook: { steps: [{ click: 'button:has-text("Register Asset")' },
                     { fill: '#a-asset-id', value: 'WH-LAND-PROBE' },
                     { fill: '#a-name', value: 'land probe asset' }],
             submit: '#asset-submit-btn' },
  inventory: { steps: [{ click: 'button:has-text("Add Part")' },
                       { fill: '#f-part-number', value: 'WH-LAND-PROBE' },
                       { fill: '#f-part-name', value: 'land probe part' },
                       { fill: '#f-qty', value: '1' }],
               submit: '#part-submit-btn' },
  community: { steps: [{ click: '#fab-post' },
                       { fill: '#post-content', value: 'land probe post' }],
               submit: '#btn-submit-post' },
  // The CAPTURE modal, reachable only after seven gates — ported verbatim from the what_happens_next flow
  // that proved it. The two provers now share one description of this path, so they cannot drift apart the
  // way my scratch diagnostic and the prover did (the selects existed in one, not the other, and the
  // disagreement read as the page's fault).
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
    submit: '#save-entry-btn', submitVia: 'requestSubmit', submitForm: '#log-form' },
  skillmatrix: { steps: [], submit: 'button:has-text("Save Targets")' },
  'asset-hub': { steps: [
      // Same three gates the double-fire flow had to learn: detail via an IN-PAGE click (a Playwright
      // click is intercepted), then the opt-in Reliability Workbench, which ships display:none.
      { eval: "document.querySelector('.asset-card') && document.querySelector('.asset-card').click()" },
      { click: '#asset-view-toggle' },
      { click: '[data-tab="fmea"]' },
      { click: '#fmea-add-btn' },
      { fill: '#fmea-function', value: 'land probe function' },
      { fill: '#fmea-failure-mode', value: 'land probe mode' }],
    submit: '#fmea-save' },
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
    pressVia: 'dom',   // measured: a coordinate click never reached rerunPlan
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
    submit: '#sheet-save-btn' },
  'pm-scheduler': { steps: [
      { click: '#tab-add' },
      { fill: '#w-name', value: 'WH Land Probe Asset' },
      { fill: '#w-tag', value: 'WH-LAND-PM' },
      { fill: '#w-location', value: 'Probe Bay' },
      { select: '#w-category', index: 1 },
      { advance: 3 }],
    submit: '#btn-save-asset' },
  assistant: { steps: [{ fill: '#chat-input', value: 'land probe' }], submit: '#send-btn' },
};

const browser = await chromium.launch();
const report = { ran: new Date().toISOString(), origin: ORIGIN, delayMs: DELAY_MS, pages: {} };
for (const p of (ONE ? [ONE] : Object.keys(FLOWS))) {
  const flow = FLOWS[p];
  const rec = { page: p };
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  await ctx.addInitScript(DELAY_WRITES, DELAY_MS);
  const page = await ctx.newPage();
  try {
    await page.goto(`${ORIGIN}/${flow.page || p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(4200);
    for (const st of flow.steps) {
      if (st.wait) {
        await page.waitForTimeout(st.wait);
      } else if (st.eval) {
        // DO NOT SWALLOW A FAILED REACH. A swallowed eval error made this prover report "the page
        // produced no action" three runs in a row when the truth was that MY setup step had thrown
        // (markDone needs an open asset). A broken reach must read as UNGRADED, never as a page defect.
        await page.evaluate(st.eval).catch((e) => {
          throw new Error('setup step failed: ' + String(e && e.message || e).slice(0, 120));
        });
      } else if (st.select) {
        await page.evaluate(({ sel, i }) => {
          const e = document.querySelector(sel);
          if (e && e.options && e.options.length > i) {
            e.selectedIndex = i; e.dispatchEvent(new Event('change', { bubbles: true }));
          }
        }, { sel: st.select, i: st.index }).catch(() => {});
      } else if (st.advance) {
        for (let i = 0; i < st.advance; i++) {
          await page.evaluate(() => {
            const b = [...document.querySelectorAll('button')]
              .find((e) => /^next/i.test((e.innerText || '').trim()) && !e.disabled && e.offsetParent !== null);
            if (b) b.click();
          }).catch(() => {});
          await page.waitForTimeout(800);
        }
      } else if (st.fill) {
        await page.fill(st.fill, st.value, { timeout: 6000 }).catch(() => {});
      } else {
        await page.click(st.click, { timeout: 6000 }).catch(() => {});
      }
      await page.waitForTimeout(450);
    }
    await page.evaluate(() => { window.__whLand.count = 0; window.__whLand.settled = 0; });
    // ★THE WINDOW MUST START BEFORE THE PRESS, NOT MID-FLIGHT. Sampling 600ms after the click missed
    // every OPTIMISTIC UI: dayplanner closes its modal the instant Save is pressed and queues the write,
    // so the dialog had already gone before the first snapshot and the settle produced no further change
    // — which my first run reported as "nothing a person could perceive changed". That was false. What a
    // person experiences is the whole span from PRESS to LANDED, so that is the span measured; a page
    // that answers immediately answers, and one that answers only at settle also answers.
    const before = await page.evaluate(SNAP);
    if (flow.submitVia === 'requestSubmit') {
      // requestSubmit is explicit about form+button; a plain click works identically (verified).
      await page.evaluate(({ f, b }) => {
        const form = document.querySelector(f); const btn = document.querySelector(b);
        if (form && typeof form.requestSubmit === 'function') form.requestSubmit(btn || undefined);
        else if (btn) btn.click();
      }, { f: flow.submitForm, b: flow.submit }).catch(() => {});
    } else {
      await pressCtl(page, flow.submit, flow.pressVia).catch(() => {});
    }
    await page.waitForTimeout(600);                       // mid-flight: the write is still held
    const fired = await page.evaluate(() => window.__whLand.count);
    if (!fired) {
      rec.status = 'UNGRADED';
      rec.why = 'the submit produced no mutating request, so no action landed for the page to report on';
    } else {
      // ★WAIT FOR THE ACTION TO ACTUALLY SETTLE, NOT FOR A GUESSED INTERVAL. A fixed
      // DELAY_MS + slack assumes ONE request, and assistant issues THREE in sequence
      // (analytics_events -> semantic-search -> ai-gateway); at 2.5s each the reply lands ~7.5s in, long
      // after a 3.9s wait. The page had answered perfectly and my probe had simply stopped watching -
      // and because the last hop is an edge function, that impatience presented as "the contract is
      // unfaithful" rather than as the timing bug it was. So poll until every intercepted request has
      // settled and the page has had a beat to react, with a hard cap so a genuinely hung action still
      // terminates.
      // ★AND SAMPLE ACROSS THE WINDOW, BECAUSE THE ANSWER IS OFTEN TRANSIENT. Waiting for settle and
      // then reading ONCE broke logbook: its confirmation is a TOAST ("WH-LAND-PROBE submitted for
      // supervisor approval"), which had appeared AND FADED before the later snapshot, so a page that
      // told the person clearly read as silent. A message that shows for three seconds is still a
      // message. So the surface is polled throughout and any confirmation seen at ANY point is kept.
      const deadline = Date.now() + DELAY_MS * 6 + 4000;
      let seenLive = '';
      let minDialogs = before.openDialogs;
      let maxDelta = 0;
      const beforeByKey = new Map((before.liveNodes || []).map((n) => [n.key, n.text]));
      const seenNodes = [];
      for (;;) {
        const st = await page.evaluate(() => ({ c: window.__whLand.count, s: window.__whLand.settled }));
        const now = await page.evaluate(SNAP);
        if (now.liveText && now.liveText !== before.liveText) seenLive = now.liveText;
        // ★CARRY THE NODES, NOT JUST THE JOINED TEXT. The peak-fold below rebuilds a synthetic snapshot, and
        // when liveNodes was added to SNAP it was NOT added here — so DIFF read b.liveNodes as undefined and
        // no confirmation could ever qualify. community's reply posted "+10 XP · Reply posted! 💪" into #toast
        // and this prover reported that NOTHING a person could perceive had changed, while the sibling prover
        // read the same toast fine. A fold that drops the field the comparison depends on is worse than no
        // fold, because it looks like evidence of absence.
        for (const n of (now.liveNodes || [])) {
          const prev = beforeByKey.get(n.key);
          if (prev === undefined || (/toast|alert/i.test(n.key) && prev !== n.text)) {
            if (!seenNodes.some((x) => x.key === n.key && x.text === n.text)) seenNodes.push(n);
          }
        }
        minDialogs = Math.min(minDialogs, now.openDialogs);
        maxDelta = Math.max(maxDelta, Math.abs(now.contentLen - before.contentLen));
        if (st.s >= st.c && st.c > 0 && Date.now() > deadline - DELAY_MS * 5) break;
        if (Date.now() > deadline) break;
        await page.waitForTimeout(400);
      }
      await page.waitForTimeout(1200);                    // let the page render what it received
      const after = await page.evaluate(SNAP);
      const settled = await page.evaluate(() => window.__whLand.settled);
      const edge = await page.evaluate(() => window.__whLand.edge);
      // Fold the peak-of-window observations in, so a transient confirmation is not lost to timing.
      const peak = {
        liveText: seenLive || after.liveText,
        // Anything that announced itself at ANY point in the window, plus whatever is on screen at the end.
        liveNodes: seenNodes.length ? seenNodes.concat(after.liveNodes || []) : (after.liveNodes || []),
        openDialogs: Math.min(minDialogs, after.openDialogs),
        busy: after.busy,
        contentLen: Math.abs(after.contentLen - before.contentLen) >= maxDelta
          ? after.contentLen : before.contentLen + maxDelta,
      };
      const reasons = DIFF(before, peak);
      rec.fired = fired; rec.settled = settled; rec.edge = edge;
      // ★A SYNTHETIC ANSWER IS ONLY FAITHFUL WHERE THE CONTRACT IS KNOWN. PostgREST's shape is fixed and
      // documented — 201 plus a representation array for an insert — so standing in for it runs the
      // page's genuine success path. An EDGE FUNCTION's response is application-specific, and a generic
      // echo is not that function's answer: report-sender rendered "All reports failed" purely because my
      // stub was not what scheduled-agents returns, and assistant had nothing renderable at all. Grading
      // either as a product defect would be blaming the page for my fixture. So an edge-backed action
      // whose surface did not change is UNGRADED, with the reason, until a contract-faithful stub exists.
      rec.status = reasons.length ? 'PASS' : (edge ? 'UNGRADED' : 'FAIL');
      rec.why = reasons.length
        ? `after the write landed, the surface changed perceptibly — ${reasons.join('; ')}`
        : (edge
          ? 'this action goes through an EDGE FUNCTION, whose response contract is application-specific. '
            + 'The synthetic answer used here is faithful to PostgREST, not to that function, so the page '
            + 'had no valid payload to render and its real success path never ran. UNGRADED rather than '
            + 'failed: the silence measured belongs to the stub, not to the product. Needs a faithful '
            + 'stub for this function before the row can be graded.'
          : 'the write landed and NOTHING a person could perceive changed: no message, no dialog close, '
            + 'no content change — they are left guessing whether it took');
      rec.before = before; rec.after = after;
    }
  } catch (e) {
    rec.status = 'UNGRADED'; rec.why = 'probe error: ' + String(e).slice(0, 90);
  }
  report.pages[p] = rec;
  console.log(`  ${p.padEnd(16)} ${String(rec.status).padEnd(9)} ${rec.why || ''}`.slice(0, 165));
  await ctx.close();
}
writeFileSync('did_it_land_report.json', JSON.stringify(report, null, 1));
const v = Object.values(report.pages);
console.log(`\n  wrote did_it_land_report.json — ${v.filter((x) => x.status === 'PASS').length} pass, `
  + `${v.filter((x) => x.status === 'FAIL').length} fail, ${v.filter((x) => x.status === 'UNGRADED').length} ungraded`);
console.log('  NO WRITE REACHED THE DATABASE: every mutating request was intercepted and answered in-page.');
await browser.close();
