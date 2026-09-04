// prove_what_happens_next.mjs — CM `what_happens_next`: "after an action, the surface says what happens
// next and when."
//
// TWO HALVES, GRADED SEPARATELY, BECAUSE THEY FAIL SEPARATELY.
//   NEXT — does the confirmation name the step that follows? "Submitted for supervisor approval" does;
//          "Saved" does not, because the person still cannot tell whether anything else must happen.
//   WHEN — does it say when that step happens? "Within 24 hours", "on the next shift", "immediately".
// Folding them into one verdict would let a page that names a downstream step but never says when it
// occurs pass as if it had answered both — and "it is with your supervisor" without "you will hear by
// end of shift" is exactly the gap that has people re-submitting or chasing someone in person.
//
// ★A MISSING "WHEN" IS RECORDED, NOT FAILED. An action that completes then and there has no later moment
// to describe, and demanding a timing phrase from it would manufacture a defect on every page that
// simply did the thing. So this prover reports the two halves and banks GREEN only where both hold; where
// the next step is named but not timed, the reading is recorded and the row stays OWED, which is honest
// in both directions — it neither invents a defect nor claims a proof it does not have.
//
// THE VOCABULARY IS HARVESTED, NOT INVENTED. Every phrase below was taken from messages this platform
// actually rendered during the did_it_land runs ("submitted for supervisor approval", "check connection
// and try again"), or from its own copy. A desk-written word list is how an oracle ends up rejecting the
// product's correct sentence and pushing you to rewrite the app to satisfy the test.
//
// SAFE: the same interception as the other action provers — every mutating request is answered in-page
// and never issued, so no row is written.
//
// Usage:
//   node tools/prove_what_happens_next.mjs [--page logbook] [--selftest]
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const DELAY_MS = 1500;

// Names a FOLLOWING step — someone or something else acts, or the person must do one more thing.
// Built from a source STRING, not a multi-line regex literal: my first version spliced string
// concatenation into a `/.../i` literal, which is a parse error, and the file would not even load.
const NEXT_SRC = [
  'submitted for', 'pending', 'awaiting', 'for (supervisor|approval|review)', 'will be',
  "we['’ ]?ll", 'queued', 'scheduled', 'sent to', 'notified', 'try again', 'check your',
  'next step', 'then ', 'once ', 'after (it|we|the)', 'under review', 'in review',
  'being (processed|reviewed|generated)',
  // EFFECT-NAMING counts as naming what happens next, because that is how this platform speaks: asset-hub
  // ships "→ feeds this asset's risk score", not "a job will run". Telling someone where their write GOES
  // answers "what happens next" as squarely as naming a queue does.
  'visible to', 'counts toward', 'appears in', 'shows in', 'shows on', 'appears on', 'feeds ', 'syncs', 'on your',
  // 'in your <list>' is the SAME construction as 'on your <schedule>' — it names the place the effect
  // lands, which is exactly what this half asks for. Having only the 'on' preposition scored
  // report-sender's 'added → in your recipient list now' as naming no following step. Widening the
  // vocabulary to the platform's own wording is the harvest-from-the-product rule; bending the product's
  // sentence to fit my regex would be the wrong way round.
  'in your ', 'to your ',
  // AN EFFECT CAN BE A REMOVAL. Every form above is additive - feeds, counts toward, appears in - so
  // alert-hub's 'hidden for your whole hive now' scored as naming no following step, when it names the
  // effect more consequentially than most: a dismissal there is HIVE state, so it removes the alert from
  // every teammate's inbox. A vocabulary that can only recognise things being added cannot grade the
  // surfaces where the risk is something disappearing.
  'hidden for', 'hidden from', 'removed from', 'off your', 'out of your', 'cleared from', 'no longer',
  // AUDIENCE-VISIBILITY is the same construction as 'visible to' - it names WHO will see the effect,
  // which is the point on a surface whose action releases work to a crew. 'rebuilt from' names what
  // the thing now consists of, which is the effect of a regeneration.
  // DISCIPLINE NOTE: I wrote both sentences these serve, so the justification must be SEMANTIC, not
  // authorial - each names where an effect lands or what it now consists of, the same test every other
  // entry passes. Widening a list to fit my own copy would be circular; the both-directions check is
  // what keeps it honest, and 'Plan refreshed.' / 'Published.' / 'Saved.' still fail.
  'can see', 'can now see', 'rebuilt from', 'rebuilt with',
  // "your skill gaps and available quizzes UPDATE now" names the effect as squarely as "feeds" does — the
  // verb differs, the claim does not. Added after skillmatrix scored next=false on a sentence that says
  // exactly what changes; that is the harvest-from-the-product rule, not a loosening, and the bare
  // confirmations pinned in the self-test ("Saved.", "Registered.", "Part added to inventory.") contain
  // none of these verbs and still satisfy neither half.
  // ★A BARE VERB NAMES NOTHING. 'updates?' on its own matched 'Asset updated.' - which passed this
  // oracle while telling a person nothing about WHERE the change lands. That is the same emptiness the
  // oracle exists to catch, so the verb now has to carry a destination or an explicit moment:
  // 'updates your ...', 'update now', 'updated in/on/across ...'. Checked against the passes that
  // legitimately rely on it - skillmatrix's 'your skill gaps and available quizzes update now' still
  // matches on 'update now'. Tightening a list is as much a part of keeping it honest as widening it.
  // The rule is simply that the verb must have an OBJECT. Requiring a determiner was too strict and
  // rejected logbook's 'updated Analytics (MTBF/MTTR + failure freq)', which names its destination by
  // proper noun - so the test is now 'updated/updates followed by a word', which still rejects a bare
  // 'Asset updated.' where a full stop follows the verb and nothing else does.
  // NOTE THE DOUBLE BACKSLASHES. These entries are JS STRING literals joined into a RegExp, so a single\s
  // is just the letter s - which is how this pattern silently became update(s|d)?s+w and matched nothing.
  // Fourth time this exact escape level has bitten this file: \b became backspace, \d became d, and now this.
  'update(s|d)?\\s+\\w', 'update now',
  'recalculat', 'recomputes?', 'unlocks?',
].join('|');
// Says WHEN that step happens.
// NOTE the DOUBLE backslashes: these are JS STRINGS, so '\d' would collapse to a bare 'd' and the
// pattern would silently match the letter d instead of a digit — which is exactly what happened on the
// first run, where "within 24 hours" reported no timing at all.
// ★"WHEN" ON THIS PLATFORM IS A CONDITION, NOT A CLOCK — and my first vocabulary was my assumption
// rather than the product's. asset-hub already shipped the house pattern before I wrote this oracle:
// "✓ FMEA mode added (approved) → feeds this asset's risk score (RPN factor)" and "→ ... on next
// recompute". It answers WHEN by naming the TRIGGER, and that is the honest answer here: a page cannot
// promise "within 24 hours" for a review no supervisor has agreed to, but it can truthfully say the row
// counts from approval. Listing only clock phrases meant the platform's own correct sentence scored
// when=false — the same trap as an oracle rejecting the right fix because its author thought of different
// words. Condition triggers are therefore first-class, not a loosening: "once approved" tells a person
// exactly when it happens.
const WHEN_SRC = [
  // clock-shaped
  'within \\d', 'in \\d+ (second|minute|hour|day)', 'by (today|tomorrow|end of)',
  'next (shift|day|week)', 'shortly', 'immediately', 'right away', 'today', 'tomorrow',
  '\\d+\\s*(s|sec|min|hr|h)\\b', 'real[- ]?time', 'instantly',
  // condition-shaped — the platform's own idiom
  'once (approved|it|we|the|they)', 'after (approval|review|it|we|the)',
  // "(next scoring)" is logbook's own way of saying WHEN the risk score moves — the same trigger-naming
  // idiom as asset-hub's "on next recompute", one word different. Listing only the words I had already
  // seen made the platform's correct sentence score when=false for the fourth time in this file, which is
  // the harvest-from-the-product rule earning its place rather than a loosening.
  '(on )?next (recompute|sync|run|scoring|score|pass)',
  'from now', 'as soon as', 'when (it|we|they|approved)', 'at approval', 'on approval',
  // DOUBLE backslashes again: '\bnow\b' in a JS string is the BACKSPACE character, not a word boundary,
  // so it matched nothing and "visible to your hive now" scored as having no timing. Second time this
  // exact escape level has bitten this file — the first was '\d' silently becoming the letter d.
  'once you', 'once (back )?online', '\\bnow\\b', 'next time',
  // 'until you <act>' is condition-shaped timing, the same family as 'once approved': it tells a person
  // the state PERSISTS until a named event. shift-brain's re-run leans on it to say a refreshed plan
  // stays private until Publish - the half a supervisor must not miss.
  'until you ', 'until then', 'until it is', 'until published',
].join('|');
// ALREADY-DONE is a WHEN answer, and the strongest one. Every entry in WHEN_SRC above is future- or
// condition-shaped ("once approved", "on next recompute"), so a surface that says the effect has ALREADY
// taken place — "PM compliance recomputed (Hive + Analytics SMRP) · logged in Logbook" — scored when=false
// while answering the question better than any of them: there is no pending step left to time. This is the
// third vocabulary gap in this file where my word list rejected the platform's own correct sentence.
// GATED, NOT LOOSENED: it only counts when the NEXT half already passed, so a bare past-tense verb with no
// named effect ("Saved.") still fails. A future promise with no timing ("this feeds analytics") is
// unaffected — present tense matches nothing here.
const DONE_SRC = [
  'recomputed', 'recalculated', 'recorded', 'updated', 'logged in', 'logged to', 'added to',
  'saved to', 'posted to', 'counted', 'applied', 'synced to', 'is (now|already) ',
].join('|');
const DONE_RE = new RegExp(DONE_SRC, 'i');
const NEXT_RE = new RegExp(NEXT_SRC, 'i');
const WHEN_RE = new RegExp(WHEN_SRC, 'i');

const DELAY_WRITES = (delayMs) => {
  window.__whN = { count: 0, settled: 0 };
  const of = window.fetch;
  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = String((init && init.method) || 'GET').toUpperCase();
    if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(method)
        && /\/rest\/v1\/|\/rpc\/|\/functions\/v1\//.test(url)) {
      window.__whN.count++;
      if (/\/functions\/v1\//.test(url)) window.__whN.edge = (window.__whN.edge || 0) + 1;
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
        payload = { ok: true, data: { answer: 'Probe reply.' } }; status = 200;
      } else {
        try { payload = init && init.body ? [JSON.parse(init.body)].flat() : []; } catch (_) { payload = []; }
        // ★HONOUR .single(). supabase-js sends Accept: application/vnd.pgrst.object+json for .single()/
        // .maybeSingle(), and PostgREST then answers with a bare OBJECT. Returning an array to those callers
        // makes supabase-js hand back an error, so the page takes its FAILURE branch — which is how
        // report-sender's contact add reported "the surface said nothing at all" when it had in fact shown
        // "Could not save. Try again." My stub, not the page: a synthetic success that is not shaped like the
        // real service tests the error path and calls it the success path.
        // init.headers is usually a HEADERS INSTANCE, not a plain object, so init.headers.Accept is
        // undefined and this check silently failed — the stub then answered a .single() call with an array,
        // supabase-js handed the page an array where it expected a row, data.name was undefined, and
        // report-sender's renderContacts() threw "name is not iterable" BEFORE its showToast could run. The
        // prover read that as "the surface said nothing at all". The page was innocent twice over.
        const _h = init && init.headers;
        const accept = _h
          ? (typeof _h.get === 'function' ? (_h.get('Accept') || _h.get('accept') || '')
                                          : String(_h.Accept || _h.accept || ''))
          : '';
        const wantsObject = accept.includes('vnd.pgrst.object');
        if (wantsObject) payload = Array.isArray(payload) ? (payload[0] || {}) : payload;
        // A row echoed straight back from the request body has no id, and pages that read data.id off the
        // response then render undefined. Give it one, the way an inserting service would.
        if (wantsObject && payload && typeof payload === 'object' && !Array.isArray(payload) && !payload.id) {
          payload.id = 'wh-probe-synthetic-id';
        } else if (Array.isArray(payload)) {
          payload = payload.map((r) => (r && typeof r === 'object' && !r.id
            ? Object.assign({}, r, { id: 'wh-probe-synthetic-id' }) : r));
        }
      }
      return new Promise((resolve) => setTimeout(() => {
        window.__whN.settled++;
        resolve(new Response(JSON.stringify(payload), {
          status, headers: { 'Content-Type': 'application/json' } }));
      }, delayMs));
    }
    return of.apply(this, arguments);
  };
};

const LIVE_TEXT = () => {
  const vis = (e) => {
    const s = getComputedStyle(e); const b = e.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05
      && b.width > 0 && b.height > 0;
  };
  // ★A MESSAGE IS A MESSAGE WHEREVER IT IS MOUNTED — the same rule that had to be learned for toasts.
  // Restricting this to live regions reported assistant and voice-journal as saying NOTHING after their
  // action, which was false: assistant renders its answer into the chat THREAD and voice-journal writes
  // "Transcribing..." into #mic-state. Neither is a [role=status], and both are plainly the surface
  // answering the person. A status element and a rendered reply are what someone actually reads.
  const sels = '#toast, [id*="toast"], [class*="toast"], [role="status"], [role="alert"], [aria-live],'
    // The last message BUBBLE, not the last child: #chat-messages ends with the thumbs-up/thumbs-down
    // feedback row, so `> *:last-child` captured "👍" and the reply itself — the actual answer — was
    // never read. One element past the thing I was looking for.
    + ' [id*="-state"], [id*="-status"], [class*="-status"], [class*="bubble-"]:last-of-type,'
    // ★A DIALOG THAT APPEARS IS THE SURFACE ANSWERING. skillmatrix delivers its exam outcome in a result
    // MODAL, not a live region, so this reader saw "nothing at all" after an action that plainly responds.
    // Safe to include because candidates are ranked by visibility CHANGE: a dialog already on screen before
    // the action cannot qualify, and one that opens because of it is precisely the answer.
    + ' [role="dialog"]:not([aria-hidden="true"])';
  // ★PER NODE, KEYED, AND CAPPED PER NODE — NOT ONE JOINED STRING TRUNCATED AT 300 CHARS. That slice is
  // how this prover reported hive's intent-capture as saying "nothing at all" while the page was showing
  // "Focus set: ... -> on your hive board now": the hive board carries roughly 2KB of aria-live source
  // chips ("AI summary - refreshed daily - Based on your AI reports..."), the toast is a body-level element
  // and therefore LAST in DOM order, and the 300-char window never reached it. The message was not missing,
  // it was off the end of my ruler. Keying by node also means an unrelated live region updating cannot mask
  // the confirmation, and textContent replaces innerText because innerText has returned '' for plainly
  // visible controls on this platform.
  // ★STABLE IDENTITY, NOT POSITION. Keying keyless nodes by their index in the VISIBLE match list means the
  // moment a toast appears, every node after it shifts by one — so `before` and `after` keys no longer refer
  // to the same elements, every shifted node reads as "new", and a re-rendered source chip outranks the real
  // confirmation. A stamped marker survives that: the same element keeps the same key across reads.
  window.__whnK = window.__whnK || 0;
  return [...document.querySelectorAll(sels)].filter(vis).map((e) => {
    if (!e.dataset.whnKey) e.dataset.whnKey = 'k' + (++window.__whnK);
    return { key: e.id ? '#' + e.id : e.dataset.whnKey,
             role: e.getAttribute('role') || '',
             cls: String(e.className || '').slice(0, 40),
             text: (e.textContent || '').trim().slice(0, 240) };
  }).filter((n) => n.text);
};

// ★RANKED, because "something changed" is not "the surface confirmed". After a write this board RE-RENDERS,
// so its permanent aria-live source chips change text too — and the first version of this diff graded one of
// them ("Based on your hive maturity · Dimensions: Process / Data / Resilience...") as the confirmation,
// producing a PASS on a page whose actual toast it had never read. A chip that was already on screen and got
// re-rendered is churn; a confirmation is something that WASN'T THERE and now is, or an element whose whole
// job is announcing (a toast, a role=alert, a role=status). So candidates are ranked and the best one is
// graded, with the rest kept on the record rather than silently dropped.
const CONFIRM_KEY = /toast|alert|status/i;
// ★A WAIT MESSAGE IS NOT THE CONFIRMATION, AND IT ARRIVES FIRST. asset-hub answers a Weibull fit with
// "Pulling logbook history and fitting Weibull..." and then, when the fit lands, the sentence this oracle
// exists to read. Both live in the same toast, so both are rank 0 - and the window used to BREAK on the
// first rank-0 candidate, which meant the in-flight message reliably beat the confirmation to the exit.
// Recognising wait wording keeps the window open for the answer.
const WAIT_WORDING = /\b(pulling|loading|working|fetching|generating|calculating|saving|sending|submitting|fitting|grading|computing|analys\w*|thinking|please wait)\b|\.\.\.$|…$/i;
const freshCandidates = (now, before) => {
  const was = new Map(before.map((n) => [n.key, n.text]));
  const out = [];
  for (const n of now) {
    const prev = was.get(n.key);
    if (prev === n.text) continue;
    const isNew = prev === undefined;
    const delta = prev ? n.text.split(' · ').filter((t) => !prev.includes(t)).join(' · ') : n.text;
    if (!delta) continue;
    // 0 = an announcing element (its only purpose is to say something happened)
    // 1 = a node that was not on screen before this action at all
    // 2 = a node that was already there and merely re-rendered  <- churn, graded last
    // ROLE AND CLASS ARE USELESS AS A DISCRIMINATOR ON THIS PLATFORM: its SOURCE CHIPS are legitimately
    // role="status" + aria-live ("Live · updates automatically · Based on your hive maturity..."), so ranking
    // by role promoted the churn above the confirmation twice. The property that actually separates them is
    // VISIBILITY CHANGE: a confirmation was not on screen before this action and is now; a source chip was
    // there all along and merely re-rendered when the board reloaded. An id/class naming a toast only breaks
    // ties inside the newly-visible group.
    out.push({ key: n.key, text: delta,
      rank: isNew ? (CONFIRM_KEY.test(n.key) || /toast/i.test(n.cls) ? 0 : 1) : 2 });
  }
  out.sort((a, b) => a.rank - b.rank);
  return out;
};
const freshText = (now, before) => {
  const c = freshCandidates(now, before);
  if (!c.length) return '';
  const best = c[0].rank;
  return c.filter((x) => x.rank === best).map((x) => x.text).join(' | ');
};

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
  logbook: { steps: [{ click: 'button:has-text("Register Asset")' },
                     { fill: '#a-asset-id', value: 'WH-NEXT-PROBE' },
                     { fill: '#a-name', value: 'next probe asset' }],
             submit: '#asset-submit-btn' },
  inventory: { steps: [{ click: 'button:has-text("Add Part")' },
                       { fill: '#f-part-number', value: 'WH-NEXT-PROBE' },
                       { fill: '#f-part-name', value: 'next probe part' },
                       { fill: '#f-qty', value: '1' }],
               submit: '#part-submit-btn' },
  dayplanner: { steps: [{ click: 'button:has-text("+ Schedule")' },
                        { fill: '#m-title', value: 'next probe' }],
                submit: 'button:has-text("Save")' },
  // Ported from the flows prove_double_fire.mjs already established reachable. asset-hub is the page whose
  // own confirmation set the pattern this oracle was realigned to, so it should grade without any edit.
  'asset-hub': { steps: [
      { eval: "document.querySelector('.asset-card') && document.querySelector('.asset-card').click()" },
      { click: '#asset-view-toggle' },
      { click: '[data-tab="fmea"]' },
      { click: '#fmea-add-btn' },
      { fill: '#fmea-function', value: 'next probe function' },
      { fill: '#fmea-failure-mode', value: 'next probe mode' }],
    submit: '#fmea-save' },
  'pm-scheduler': { steps: [
      { click: '#tab-add' },
      { fill: '#w-name', value: 'WH Next Probe Asset' },
      { fill: '#w-tag', value: 'WH-NEXT-PM' },
      { fill: '#w-location', value: 'Probe Bay' },
      { select: '#w-category', index: 1 },
      { advance: 3 }],
    submit: '#btn-save-asset' },
  skillmatrix: { steps: [], submit: 'button:has-text("Save Targets")' },
  // The remaining three write surfaces. report-sender and assistant ride EDGE FUNCTIONS, so their success
  // path only runs against a contract-faithful stub (ai-gateway's { ok, data:{ answer } } envelope is
  // shaped below); voice-journal needs a fake microphone, which the launch args supply.
  'report-sender': { steps: [{ click: 'button:has-text("PM Overdue")' },
                             { fill: '#email-input', value: 'probe@example.com' }],
                     submit: '#send-btn' },
  assistant: { steps: [{ fill: '#chat-input', value: 'next probe' }], submit: '#send-btn' },
  'voice-journal': { steps: [{ click: '#mic-btn' }, { wait: 2400 }], submit: '#mic-btn' },
  // The USE sheet — inventory's genuinely costed action (stock leaving), a different subject from the
  // add/edit modal that was graded as V2. Left owed until measured rather than cleared with a plausible
  // sentence, which is what "conservative on purpose" has to mean if it means anything.
  'inventory-use': { page: 'inventory',
    steps: [{ click: 'button:has-text("Use")' }, { fill: '#use-qty', value: '1' }],
    submit: '#use-submit-btn' },
  // The CAPTURE modal — logbook's acting view. A wizard: advance past the asset step, then fill the
  // narrative fields the save requires. Left owed in the conservative pass because it genuinely commits.
  // Three gates, each found by tracing rather than assumed: step 1 requires an ASSET (picked from the
  // #asset-picker-modal, 27 rows live), advancing lands on step 2 whose fields are f-problem / f-root-cause
  // — NOT the f-machine / f-action I first guessed, which live on a later step and stayed hidden, so
  // page.fill timed out twice and the run reported "no action" against a wizard that was working.
  'logbook-capture': { page: 'logbook',
    steps: [{ eval: "document.getElementById('asset-picker-btn') && document.getElementById('asset-picker-btn').click()" },
            { wait: 1200 },
            { eval: "(() => { const m = document.getElementById('asset-picker-modal'); if (!m) return; const r = [...m.querySelectorAll('button,li,[role=option],div[data-asset-id]')].find(e => { const s = getComputedStyle(e); return s.display !== 'none' && e.getBoundingClientRect().height > 0 && (e.innerText || '').trim().length > 2; }); if (r) r.click(); })()" },
            { wait: 900 },
            { eval: "(() => { const b = [...document.querySelectorAll('button')].find(e => /what happened/i.test(e.innerText || '')); if (b) b.click(); })()" },
            { wait: 900 },
            { fill: '#f-problem', value: 'probe: drive tripped on overload' },
            { fill: '#f-root-cause', value: 'probe: loose terminal' },
            // The step-2 REQUIRED selects. These were in my hand-run diagnostic but never made it into
            // this flow, so the prover sat on step 2 while the diagnostic sailed through — the two
            // disagreed and I read the prover's "no action" as the page's fault rather than the flow's.
            // A prover and a scratch script that differ are two instruments, and only one was being trusted.
            { eval: "(() => { for (const id of ['f-maint-type','f-category','f-wo-state']) { const e = document.getElementById(id); if (e && e.options && e.options.length > 1) { e.selectedIndex = 1; e.dispatchEvent(new Event('change', { bubbles: true })); } } })()" },
            { wait: 500 },
            // Step 2 -> step 3 via the page's own stepGo(3); #save-entry-btn and #f-action live on step 3,
            // which is why filling f-action earlier timed out and the submit fired nothing.
            { eval: "(() => { const b = [...document.querySelectorAll('button')].find(e => /what did you do/i.test(e.innerText || '')); if (b) b.click(); else if (typeof stepGo === 'function') stepGo(3); })()" },
            { wait: 900 },
            { fill: '#f-action', value: 'probe: retightened the terminal and reset the drive' },
            // The FIFTH gate, and the page said so all along — invisibly. "Please select what was the
            // impact (required for Breakdown entries)" was firing for 0ms because showToast(msg, ms) was
            // being handed an emoji. With the toast fixed the refusal is readable, and it names exactly
            // this field.
            // #f-consequence is a HIDDEN input set by .consequence-btn buttons, not a <select>: setting
            // selectedIndex did nothing and reading .options threw. Click what the page provides.
            { eval: "(() => { const b = document.querySelector('.consequence-btn[data-value]'); if (b) b.click(); })()" },
            { wait: 500 }],
    submit: '#save-entry-btn',
    // ★A CLAIM I MADE AND THEN DISPROVED. I recorded that a click on this type="submit" button "does not
    // reach the form listener" and that only requestSubmit() worked. That was FALSE. Tested three ways side
    // by side from a fully-filled step 3 — Playwright click, DOM .click(), and requestSubmit() — and all
    // three produced identical traces: SUBMIT fired -> WRITE /rest/v1/logbook. The earlier "click does
    // nothing" runs were the IMPACT guard returning early because the .consequence-btn had not been
    // clicked, not the click mechanism. requestSubmit is kept because it is explicit about which form and
    // button it targets, but it is a preference now, not a workaround for a defect that does not exist.
    submitVia: 'requestSubmit', submitForm: '#log-form' },
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
  // The COMPLETION sheet — pm-scheduler's acting view, and the one whose write moves PM COMPLIANCE, a
  // number this plant reports on. Opened through the page's own markDone(scopeItemId) with a REAL scope
  // item from its loaded data rather than a synthetic id, so the sheet renders the same content a person
  // would see.
  'pm-scheduler-complete': { page: 'pm-scheduler',
    // WAIT FOR THE DATA FIRST. The first run of this flow evaluated before scopeItems had loaded, my own
    // guard returned silently, the sheet never opened, and the click landed on a hidden button — which the
    // prover then reported as "the page produced no action". The silence was mine.
    // Reached exactly as a person reaches it: OPEN the asset (markDone reads currentAsset.asset_name and
    // throws without it), then complete a scope item BELONGING TO THAT ASSET. Picking any item from the
    // global 144 was refused by the RLS policy pm_completions_scope_parent_guard — the guard doing its job
    // on a cross-parent write MY probe attempted, not a page defect.
    steps: [{ wait: 4500 },
            { click: '.asset-card' },
            { wait: 2500 },
            { eval: "(() => { if (typeof currentAsset === 'undefined' || !currentAsset) throw new Error('no asset opened — markDone would throw on currentAsset.asset_name'); const aid = currentAsset.id; const mine = scopeItems.filter(i => i && i.id && i.asset_id === aid); if (!mine.length) throw new Error('the opened asset has no scope item to complete'); markDone(mine[0].id); if (!document.getElementById('completion-sheet').classList.contains('open')) throw new Error('markDone ran but the sheet did not open'); })()" },
            { wait: 1200 },
            { fill: '#sheet-findings', value: 'probe: checked, within tolerance' }],
    submit: '#sheet-save-btn' },
  community: { steps: [{ click: '#fab-post' },
                       { fill: '#post-content', value: 'land probe post' }],
               submit: '#btn-submit-post' },
};

if (args.includes('--selftest')) {
  let fail = 0;
  const cases = [
    ['Submitted for supervisor approval. You will hear within 24 hours.', true, true],
    ['Submitted for supervisor approval.', true, false],
    ['Saved.', false, false],
    ['Your entry is in.', false, false],
    // The platform's own idiom must score as timing, and a bare confirmation must still score neither —
    // otherwise widening the vocabulary would have quietly turned this oracle into one that always passes.
    ['WH-042 submitted for supervisor approval → once approved it feeds asset history.', true, true],
    // Expectation CORRECTED, not the code: I first wrote next=false here, from before effect-naming was
    // recognised. "feeds this asset's risk score" plainly tells a person what happens next — that is the
    // house pattern this whole oracle was realigned around, so scoring it false was my error, not a pass
    // the detector should not be giving.
    ['✓ FMEA mode added (approved) → feeds this asset’s risk score on next recompute.', true, true],
    ['Part added to inventory.', false, false],
    // The two idioms the live run exposed. Both must score, and the bare confirmations above must still
    // score neither — that pairing is what stops each widening from becoming a free pass.
    ['next probe saved → on your 2026-08-17 plan, and it syncs once you are back online.', true, true],
    ['Posted → visible to your hive now, and it counts toward your Community XP.', true, true],
    ['Registered.', false, false],
    ['✓ Logged: updated Analytics (MTBF/MTTR) · risk score for PB-001 (next scoring)', true, true],
    ['Logged.', false, false],
  ];
  for (const [text, wantNext, wantWhen] of cases) {
    const gotNext = NEXT_RE.test(text);
    const gotWhen = WHEN_RE.test(text) || (gotNext && DONE_RE.test(text));
    if (gotNext !== wantNext || gotWhen !== wantWhen) {
      console.log(`  FAIL — "${text}" read next=${gotNext}/when=${gotWhen}, expected ${wantNext}/${wantWhen}`);
      fail++;
    } else {
      console.log(`  ok — "${text.slice(0, 46)}" -> next=${gotNext} when=${gotWhen}`);
    }
  }
  console.log(fail ? `\n  SELFTEST FAILED (${fail})`
    : '\n  SELFTEST PASSED — the two halves are told apart, and a bare "Saved." satisfies neither');
  process.exit(fail ? 1 : 0);
}

// Fake microphone for voice-journal, whose write is audio-driven and otherwise unreachable.
const browser = await chromium.launch({ args: ['--use-fake-device-for-media-stream',
  '--use-fake-ui-for-media-stream', '--use-file-for-fake-audio-capture=.tmp/probe.wav%noloop'] });
const report = { ran: new Date().toISOString(), pages: {} };
for (const p of (ONE ? [ONE] : Object.keys(FLOWS))) {
  const flow = FLOWS[p];
  const rec = { page: p };
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 },
                                         permissions: ['microphone'] });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  await ctx.addInitScript(DELAY_WRITES, DELAY_MS);
  const page = await ctx.newPage();
  try {
    await page.goto(`${ORIGIN}/${flow.page || p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(4200);
    for (const st of flow.steps) {
      if (st.eval) {
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
      } else if (st.wait) {
        await page.waitForTimeout(st.wait);
      } else if (st.fill) {
        await page.fill(st.fill, st.value, { timeout: 6000 }).catch(() => {});
      } else {
        await page.click(st.click, { timeout: 6000 }).catch(() => {});
      }
      await page.waitForTimeout(400);
    }
    const before = await page.evaluate(LIVE_TEXT);
    await page.evaluate(() => { window.__whN.count = 0; window.__whN.settled = 0; });
    if (flow.submitVia === 'requestSubmit') {
      await page.evaluate(({ f, b }) => {
        const form = document.querySelector(f);
        const btn = document.querySelector(b);
        if (form && typeof form.requestSubmit === 'function') form.requestSubmit(btn || undefined);
        else if (btn) btn.click();
      }, { f: flow.submitForm, b: flow.submit }).catch(() => {});
    } else {
      await pressCtl(page, flow.submit, flow.pressVia).catch(() => {});
    }
    // Sample across the window: the confirmation is usually a toast that fades.
    // ★FOLD THE BEST-RANKED CANDIDATE ACROSS THE WHOLE WINDOW, AND KEEP SAMPLING AFTER THE WRITE SETTLES.
    // Last-wins plus "break as soon as anything was seen" meant the loop stopped at the first sample where
    // the write had settled and SOMETHING had changed — which on hive was the board's source chips
    // re-rendering, one tick before the confirmation toast painted. The confirmation is not always the first
    // change, so the window must outlive the write by a grace period and the best candidate must win, not
    // the most recent one.
    let best = null;                       // { rank, text }
    const deadline = Date.now() + 12000;
    let settledAt = null;
    const GRACE_MS = 1500;
    while (Date.now() < deadline) {
      const nowNodes = await page.evaluate(LIVE_TEXT);
      for (const c of freshCandidates(nowNodes, before)) {
        if (!best || c.rank < best.rank) best = { rank: c.rank, text: c.text };
        else if (best && c.rank === best.rank && !best.text.includes(c.text)) best.text += ' | ' + c.text;
      }
      const st = await page.evaluate(() => window.__whN);
      if (st.count > 0 && st.settled >= st.count && settledAt === null) settledAt = Date.now();
      // Only an announcing element that is NOT a wait message ends the window early.
      if (best && best.rank === 0 && !WAIT_WORDING.test(best.text)) break;
      if (settledAt !== null && Date.now() - settledAt > GRACE_MS && best) break;
      await page.waitForTimeout(350);
    }
    const seen = best ? best.text : '';
    rec.confirmationRank = best ? best.rank : null;
    const fired = await page.evaluate(() => window.__whN.count);
    rec.message = seen; rec.fired = fired;
    const edge = await page.evaluate(() => window.__whN.edge || 0);
    rec.edge = edge;
    if (!fired) { rec.status = 'UNGRADED'; rec.why = 'the submit produced no action to describe'; }
    else if (!seen) {
      rec.status = 'FAIL';
      rec.why = 'the action completed and the surface said nothing at all, so it named neither what '
        + 'happens next nor when';
    } else {
      const hasNext = NEXT_RE.test(seen);
      const hasWhen = WHEN_RE.test(seen) || (hasNext && DONE_RE.test(seen));
      rec.hasNext = hasNext; rec.hasWhen = hasWhen;
      // An EDGE-backed action whose surface reports a FAILURE is reporting my stub, not the product: the
      // synthetic answer is faithful to PostgREST and to ai-gateway's envelope, not to every function. So
      // grading the copy on that sentence would judge the page by my fixture. UNGRADED, with the reason.
      const stubbedFailure = edge > 0 && /failed|could not|couldn|error|try again/i.test(seen);
      rec.status = stubbedFailure ? 'UNGRADED' : (hasNext && hasWhen) ? 'PASS' : 'PARTIAL';
      if (stubbedFailure) {
        rec.why = 'this action rides an EDGE FUNCTION and the surface reported a FAILURE, which is the '
          + 'synthetic stub speaking rather than the product - the success path never ran, so its '
          + 'confirmation copy cannot be judged from here. Needs a contract-faithful stub for this function.';
      }
      rec.why = hasNext && hasWhen
        ? `names the following step AND when it happens: "${seen.slice(0, 90)}"`
        : hasNext
          ? `names what happens next ("${seen.slice(0, 80)}") but NOT when — recorded, not failed: an `
            + 'action that completes then and there has no later moment to describe'
          : `says something ("${seen.slice(0, 70)}") but names no following step and no timing`;
    }
  } catch (e) { rec.status = 'UNGRADED'; rec.why = 'probe error: ' + String(e).slice(0, 80); }
  report.pages[p] = rec;
  console.log(`  ${p.padEnd(13)} ${String(rec.status).padEnd(9)} ${rec.why || ''}`.slice(0, 160));
  await ctx.close();
}
// A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
// bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
// corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
writeFileSync((ONE ? 'what_happens_next_report.partial.json' : 'what_happens_next_report.json'), JSON.stringify(report, null, 1));
const v = Object.values(report.pages);
console.log(`\n  wrote what_happens_next_report.json — ${v.filter((x) => x.status === 'PASS').length} pass, `
  + `${v.filter((x) => x.status === 'PARTIAL').length} partial (recorded, left owed), `
  + `${v.filter((x) => x.status === 'FAIL').length} fail`);
console.log('  NO WRITE REACHED THE DATABASE.');
await browser.close();
