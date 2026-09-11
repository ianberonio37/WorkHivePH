// prove_reference_repaint_keeps_focus — P-D "repaint keeps focus & draft" (2026-09-05; P179 validator-catalog,
// then P172 logbook, P175 marketplace, P178 marketplace-admin, P181 hive, P187 platform-actions, P188 alert-hub).
// Two shapes of repaint, one contract: the element the person is using must survive it.
//   filter cases  - typing into a filter re-renders the list; the input keeps focus AND its text, the caret stays.
//   repaint cases - a poll/realtime handler repaints a pane while a draft is being typed elsewhere (hive coach box)
//                   or while a control inside the pane holds focus (alert-hub feed): focus must not fall to <body>
//                   and a typed draft must be intact. A repaint that replaces the focused node's ancestor throws a
//                   keyboard user to the top of the page (the logbook class, 2026-08; marketplace svc pane).
// A MutationObserver on <body> proves a repaint actually happened; a case with no observed mutation is a 'no
// repaint' verdict, never a pass.
//   node tools/prove_reference_repaint_keeps_focus.mjs            # all; exit 1 on any lost focus/draft
//   node tools/prove_reference_repaint_keeps_focus.mjs --page logbook.html
import { chromium } from 'playwright';
import { SEEDER, signIn } from './prover_harness.mjs';   // shared preamble (2026-09-05)
const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const CASES = [
  { file: 'validator-catalog.html', input: '#q', text: 'T15', wait: 6000 },
  // a supervisor lands in TEAM view: typing debounces a server search, so the repaint comes after the round-trip
  { file: 'logbook.html', input: '#search-input', text: 'pump', after: '#btn-search-team', wait: 9000, settle: 6000, signin: true },   // team view repaints only on Search Team (a debounce re-runs it afterwards)
  { file: 'marketplace.html', input: '#search-input', text: 'motor', wait: 9000, signin: true },
  { file: 'marketplace-admin.html', input: '#search-input', text: 'a', wait: 9000, signin: true },
  { file: 'platform-actions.html', input: '#fb-filter-search', text: 'a', wait: 9000, signin: true },
  // a draft typed in the coach box while the feed repaints (the realtime handler's own refetch)
  { file: 'hive.html', focus: '#feed button, #feed a, #feed [tabindex="0"]', repaint: 'loadFeed()', wait: 10000, signin: true },   // the coach box sits in a collapsed panel; the feed's own controls are what a realtime refetch rebuilds
  // no text input: a control inside the polled feed holds focus while the 60 s poll's loader repaints it
  // loadAll lives inside a closure (unreachable from eval), so the real 60 s poll tick is the repaint - wait it out
  { file: 'alert-hub.html', focus: '#feed button, #feed a, #feed [tabindex="0"]', repaint: 'wait:63000', wait: 12000, signin: true },
];

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
if (CASES.some((c) => c.signin && (!ONLY || c.file === ONLY))) await signIn(ctx);
let bad = 0, n = 0;
for (const c of CASES) {
  if (ONLY && c.file !== ONLY) continue;
  n++;
  const p = await ctx.newPage();
  const pageErrors = [];
  p.on('pageerror', (e) => pageErrors.push(e.message.slice(0, 120)));   // an n/a on a broken page is not an n/a (2026-09-05: alert-hub's feed never rendered)
  await p.goto(`${SEEDER}/workhive/${c.file}`, { waitUntil: 'load' }).catch(() => {});
  await p.waitForTimeout(c.wait);
  await p.evaluate(() => { window.__whMut = 0; new MutationObserver((m) => { window.__whMut += m.length; }).observe(document.body, { childList: true, subtree: true }); });
  if (c.open) { await p.click(c.open, { timeout: 5000 }).catch(() => {}); await p.waitForTimeout(800); }
  const target = c.input || c.focus;
  // a polled feed paints its controls after its first fetch (and a skeleton before it): wait up to 20 s for the target
  // to exist and be visible before calling it absent - an absent control is an honest n/a, never a pass
  const present = await p.waitForFunction((sel) => { const el = document.querySelector(sel); return !!(el && (typeof el.checkVisibility === 'function' ? el.checkVisibility() : el.offsetParent !== null)); }, target, { timeout: 20000 }).then(() => true).catch(() => false);
  if (!present) {
    if (pageErrors.length) { bad++; console.log(`  BAD ${c.file.padEnd(24)} ${target} not present AND the page threw: ${pageErrors[0]}`); await p.close(); continue; }
    console.log(`  n/a ${c.file.padEnd(24)} ${target} not present/visible`); n--; await p.close(); continue;
  }
  await p.evaluate((sel) => document.querySelector(sel).focus(), target);
  if (c.text) { for (const ch of c.text) { await p.keyboard.type(ch); await p.waitForTimeout(250); } }
  if (c.after) { await p.click(c.after, { timeout: 5000 }).catch(() => {}); await p.evaluate((sel) => { const el = document.querySelector(sel); if (el) el.focus(); }, target); }   // a list-driving button; the person returns to the field
  if (c.repaint && c.repaint.startsWith('wait:')) { await p.waitForTimeout(Number(c.repaint.slice(5))); }
  else if (c.repaint) { await p.evaluate((expr) => { try { const r = (0, eval)(expr); return r && r.then ? r.catch(() => {}) : r; } catch (e) { console.warn('repaint expr failed', e); } }, c.repaint); await p.waitForTimeout(3500); }
  await p.waitForTimeout(600 + (c.settle || 0));
  const r = await p.evaluate(({ sel, text }) => {
    const el = document.querySelector(sel); const a = document.activeElement;
    const isInput = el && ('value' in el) && typeof el.value === 'string';
    return { focused: a === el, activeTag: a ? (a.tagName.toLowerCase() + (a.id ? '#' + a.id : '')) : 'none', bodyFocus: !a || a === document.body, value: isInput ? el.value : null, caretAtEnd: isInput && text ? (el.selectionStart === el.value.length) : null, mut: window.__whMut, inDom: !!(el && el.isConnected) };
  }, { sel: target, text: c.text || '' });
  const repainted = r.mut > 0;
  const draftOk = c.text ? r.value === c.text : true;
  const focusOk = c.text ? r.focused : !r.bodyFocus;   // a focus-only case passes if focus stayed anywhere sensible (restored or preserved), never on <body>
  const ok = focusOk && draftOk && r.caretAtEnd !== false && repainted;
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${c.file.padEnd(24)} ${c.text ? 'typed "' + c.text + '"' : 'focused ' + target.split(',')[0]}${c.repaint ? ' + ' + c.repaint : ''} -> focus ${r.focused ? 'kept' : (r.bodyFocus ? 'LOST to body' : 'moved to ' + r.activeTag)}, draft ${c.text ? '"' + r.value + '"' : 'n/a'}, caret ${r.caretAtEnd === false ? 'JUMPED' : 'ok'}, node ${r.inDom ? 'kept' : 'REPLACED'}, mutations ${r.mut}${repainted ? '' : ' (NO repaint observed)'}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} reference-repaint-focus - ${n - bad}/${n} inputs/controls keep focus and draft through the repaint`);
process.exit(bad ? 1 : 0);
