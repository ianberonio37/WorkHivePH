// prove_flow_speaks_filipino — a flow's MESSAGES must speak the language the page is set to.
//
// ★THE GAP THIS EXISTS FOR (T45). The platform has TWO translation mechanisms and they cover
// different halves of the screen. `data-i` + whI18nApply swap STATIC markup at load — measured
// 442/442 on this platform, which is where "FIL coverage is 100%" comes from. But every message
// the FLOW produces is born AFTER that pass, from showToast(...), and showToast takes a raw
// string. The only translator for those is _t(en, fil), called by hand at the call site.
//
// So a Filipino worker opens logbook and every label is Filipino; then they tap Save and the
// refusal that decides whether their repair is recorded arrives in English. The resting page is
// fully translated and the WORKING page is not — and a load-time DOM sweep can never see it,
// because at load the message does not exist yet.
//
// THE ORACLE: run the same flow step twice, once with wh_lang=fil and once with wh_lang=en, and
// read the message the page actually shows. If the two runs produce the SAME bytes for a
// multi-word message, that message never passed through _t(). The EN control is what makes this
// a measurement rather than a guess: it separates "untranslated" from "identical in both
// languages" (a name, a code, a number), which a FIL-only run cannot tell apart.
//
// The steps below are REFUSALS — a required field left empty. Nothing is written, so the walk
// costs no rows and needs no cleanup, and a refusal is exactly the message a worker cannot
// afford to not understand.
//
// USAGE:  node tools/prove_flow_speaks_filipino.mjs [--page <name>] [--gate]
// OUTPUT: flow_speaks_filipino_report.json  (narrowed runs write their own, never the sweep's)
import { writeFileSync } from 'fs';
import { chromium } from '@playwright/test';
import { signIn, SEEDER } from './live_page_journeys.mjs';

const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const NARROW = PAGE_ONLY ? `page-${PAGE_ONLY}`.replace(/[^\w.-]+/g, '_') : '';
const REPORT = NARROW ? `flow_speaks_filipino_report.${NARROW}.json`
                      : 'flow_speaks_filipino_report.json';

// Each step names the trajectory whose core flow it stands in, the control a worker touches,
// and the refusal that control produces when a required field is empty.
// `msgSel` is for refusals that are NOT toasts: voice-journal answers an empty note by writing
// into an inline status line, which a toast-only capture reads as silence.
const STEPS = [
  // The save button lives in a collapsed step panel, so clicking it throws "not visible" — and
  // the first cut then read the toast's RESTING PLACEHOLDER ("Entry saved." is markup at line
  // 1220, not a message) and scored it. requestSubmit() runs the form's real submit handler,
  // which is the same path the button takes, and it works whichever step is showing.
  { traj: 'T9',  page: 'logbook.html',       step: 'save an entry with no asset picked',
    act: { submit: '#log-form' } },
  { traj: 'T10', page: 'pm-scheduler.html',  step: 'add a scope item with no description',
    act: { call: 'addCustomItem' } },
  // The typed-note fallback lives inside a CLOSED <details>, and a closed disclosure still
  // reports layout rects for its hidden children — so clicking #type-send without opening it
  // first lands on empty space and the page answers with silence. (It looked at first like the
  // history panel's filter chips were covering the button, because a hit-test at the button's
  // phantom rect returns whatever IS painted there. A screenshot showed the panel collapsed and
  // tidy: the overlap was my probe's, not the page's.)
  { traj: 'T12', page: 'voice-journal.html', step: 'send a typed note that is empty',
    act: { open: '#type-fallback', click: '#type-send' }, msgSel: '#type-state' },
];

// Two real words is the bar, not three: the first cut used three and scored "Entry saved." — a
// two-word English receipt shown to a Filipino worker — as if it had passed. A threshold set
// above the shortest message in the set is not a filter, it is a blind spot.
const WORDY = (s) => String(s || '').trim().split(/\s+/).filter(w => /[A-Za-z]{2,}/.test(w)).length >= 2;

async function runFlow(browser, lang, step) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await ctx.addInitScript((l) => {
    try {
      localStorage.setItem('wh_lang', l);
      // The step must own its precondition. A saved draft refills the entry form, so the first
      // run of this walk sailed past the refusal and reported "Entry saved." — the flow's happy
      // path, measured as if it were the refusal. Clear drafts so the form is genuinely empty.
      Object.keys(localStorage)
        .filter(k => k.indexOf('wh_logbook_draft_') === 0 || k.indexOf('wh_draft_') === 0)
        .forEach(k => localStorage.removeItem(k));
    } catch (_) { /* private mode */ }
  }, lang);
  const s = await signIn(ctx, 'supervisor');
  if (!s.ok) { await ctx.close(); return { err: s.err || 'sign-in unavailable' }; }
  const page = await ctx.newPage();
  try {
    await page.goto(`${SEEDER}/workhive/${step.page}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(4000);
    const applied = await page.evaluate(() => String(window.WH_LANG || ''));
    // Wrap the page's own showToast so the message is captured at the CALL, not scraped from a
    // toast that may have already timed out. A first cut read the DOM and got "" for two of three
    // steps, which the report then scored as "speaks Filipino" — an empty reading is the
    // instrument failing, never the property holding.
    await page.evaluate((sel) => {
      window.__whMsgs = [];
      const push = (m) => { try { window.__whMsgs.push(String(m)); } catch (_) {} };
      if (typeof window.showToast === 'function') {
        const orig = window.showToast;
        window.showToast = function (m) { push(m); return orig.apply(this, arguments); };
        window.__whWrapped = 'global';
      } else {
        // voice-journal declares showToast inside a closure, so there is nothing on window to
        // wrap. Watch the DOM instead — both the toast node and the step's inline status line.
        window.__whWrapped = 'observer';
        const watch = ['#toast', sel].filter(Boolean).map(s => document.querySelector(s)).filter(Boolean);
        for (const node of watch) {
          new MutationObserver(() => {
            const txt = (node.textContent || '').trim();
            if (txt && window.__whMsgs[window.__whMsgs.length - 1] !== txt) push(txt);
          }).observe(node, { childList: true, characterData: true, subtree: true });
        }
        if (!watch.length) window.__whWrapped = 'none';
      }
    }, step.msgSel || null);
    let reached = 'yes';
    if (step.act.open) {
      await page.evaluate((s) => { const d = document.querySelector(s); if (d) d.open = true; }, step.act.open);
      await page.waitForTimeout(400);
    }
    if (step.act.submit) {
      reached = await page.evaluate((s) => {
        const f = document.querySelector(s);
        if (!f) return `no form ${s}`;
        try { f.requestSubmit ? f.requestSubmit() : f.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true })); }
        catch (_) { /* the refusal is the point */ }
        return 'yes';
      }, step.act.submit);
    } else if (step.act.click) {
      const el = page.locator(step.act.click).first();
      if (!(await el.count())) reached = `no control ${step.act.click}`;
      else await el.click({ timeout: 5000, force: true }).catch(e => { reached = `click failed: ${String(e).slice(0, 40)}`; });
    } else if (step.act.call) {
      reached = await page.evaluate((fn) => {
        if (typeof window[fn] !== 'function') return `no function ${fn}`;
        try { window[fn](); } catch (_) { /* the refusal is the point */ }
        return 'yes';
      }, step.act.call);
    }
    await page.waitForTimeout(900);
    // ONLY messages observed at the moment they were produced count. There is deliberately no
    // fallback to reading the toast node at rest: #toast-text ships with "Entry saved." as
    // placeholder markup, so a resting read hands back a success receipt for a step that never
    // ran — which is exactly how the first cut reported a save that never touched the database.
    const seen = await page.evaluate(() => ({
      wrapped: window.__whWrapped,
      msgs: window.__whMsgs || [],
    }));
    await ctx.close();
    const msg = (seen.msgs.length ? seen.msgs[seen.msgs.length - 1] : '').trim();
    return { lang: applied, msg, reached, wrapped: seen.wrapped, all: seen.msgs };
  } catch (e) {
    await ctx.close();
    return { err: String(e).slice(0, 90) };
  }
}

const browser = await chromium.launch();
const steps = STEPS.filter(s => !PAGE_ONLY || s.page === PAGE_ONLY);
const rows = [];
for (const step of steps) {
  const fil = await runFlow(browser, 'fil', step);
  const en = await runFlow(browser, 'en', step);
  if (fil.err || en.err) {
    console.log(`SKIP ${step.page} — ${fil.err || en.err}`);
    rows.push({ ...step, act: undefined, skipped: fil.err || en.err });
    continue;
  }
  // NO MESSAGE — or a step that never reached its control — is an instrument failure, not a
  // pass: the run says NOTHING about language and must not be scored as if it did.
  const blind = !fil.msg || !en.msg || fil.reached !== 'yes' || en.reached !== 'yes';
  const untranslated = !blind && fil.msg === en.msg && WORDY(fil.msg);
  rows.push({ traj: step.traj, page: step.page, step: step.step, filApplied: fil.lang,
              fil: fil.msg, en: en.msg, reached: fil.reached, wrapped: fil.wrapped,
              silent: blind, untranslated });
}
await browser.close();

const bad = rows.filter(r => r.untranslated);
const silent = rows.filter(r => r.silent);
writeFileSync(REPORT, JSON.stringify({ steps: rows.length, untranslated: bad.length,
                                       noMessage: silent.length, rows }, null, 2));

console.log(`flow-speaks-filipino — flow steps ${rows.length}, English in FIL ${bad.length}, no message reached ${silent.length}`);
for (const r of rows) {
  if (r.skipped) { console.log(`    ${r.page.padEnd(20)} SKIP ${r.skipped}`); continue; }
  const verdict = r.silent ? 'NO MSG  ' : (r.untranslated ? 'ENGLISH ' : 'speaks  ');
  console.log(`    ${r.traj.padEnd(4)} ${r.page.padEnd(20)} ${verdict} "${r.fil}"${r.silent ? `   (reached: ${r.reached}, wrap: ${r.wrapped})` : ''}`);
}
if (silent.length) {
  console.log('\nFAIL — a step produced no message at all, so it proves nothing about language.');
  console.log('  Fix the walk before reading the verdict: an empty reading is the instrument.');
}
if (bad.length) {
  console.log('\nFAIL — a worker set to Filipino was refused in English. data-i translated the page at');
  console.log('  load; these messages are born after that pass, so only _t(en, fil) at the showToast');
  console.log('  call site can reach them. Wrap the message, do not widen the load-time sweep.');
}
if (bad.length || silent.length) process.exit(GATE ? 1 : 0);
console.log('\nPASS — every walked flow refuses in the language the worker chose.');
