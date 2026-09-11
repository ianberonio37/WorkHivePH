// probe_data_failure_notice — one-off runtime probe (2026-09-05): with every data read aborted, what does each page
// actually hold after 12 s? The transport notice (present? position? rect?), the frozen progress text nodes and whether
// the settle ran. Explains the degradation prover's own verdicts rather than trusting them.
import { chromium } from 'playwright';
import { SEEDER, signIn, SETTLE_MS } from './prover_harness.mjs';
const PAGES = process.argv.slice(2).length ? process.argv.slice(2) : ['hive.html', 'platform-actions.html', 'assistant.html', 'logbook.html'];
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
await signIn(ctx);
for (const file of PAGES) {
  const p = await ctx.newPage();
  const errs = [];
  p.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errs.push(m.text().slice(0, 100)); });
  await p.route('**/*', (route) => /\/rest\/v1\/|\/functions\/v1\/|\/realtime\/v1\/|\/storage\/v1\//.test(route.request().url()) ? route.abort('failed') : route.continue());
  await p.goto(`${SEEDER}/workhive/${file}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  // Call the settle DIRECTLY and report what it changed, plus which version of it the page runs (2026-09-05: 40 passes
  // completed on hive and its static 'Computing hive health...' span stayed - is the pass not matching, or is it old code?)
  const direct = await p.evaluate(() => {
    const before = (document.getElementById('ss-verdict-label') || {}).textContent || '(no #ss-verdict-label)';
    const src = typeof _whSettleStuckLoaders === 'function' ? _whSettleStuckLoaders.toString() : '(missing)';
    let err = null; try { _whSettleStuckLoaders(); } catch (e) { err = e.message; }
    const after = (document.getElementById('ss-verdict-label') || {}).textContent || '(no #ss-verdict-label)';
    const chip = document.querySelector('.wh-source-chip'); const chipText = chip ? chip.textContent.trim().slice(0, 40) : '(no chip)';
    const marked = document.querySelectorAll('[data-wh-read-failed]').length;
    const spanMarked = (document.getElementById('ss-verdict-label') || {}).getAttribute ? document.getElementById('ss-verdict-label').getAttribute('data-wh-read-failed') : null;
    const settledDelta = (window._whSettled || 0);
    const listErr = typeof whListError; const sliceOk = Array.prototype.slice.call([1, 2]).length === 2;
    const inlineHits = (() => { const PROG = /^(Computing|Loading|Counting|Reading|Rolling up|Fetching|Building)[^.]{0,90}(\.\.\.|…)\s*$/; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null); let n, h = 0; while ((n = w.nextNode())) { const t = (n.textContent || '').trim(); if (t && PROG.test(t) && n.parentElement && n.parentElement.checkVisibility()) h++; } return h; })();
    return { before: before.slice(0, 40), after: after.slice(0, 40), chipText, err, usesCheckVisibility: /checkVisibility/.test(src), hasPROG: /Computing\|Loading/.test(src), srcLen: src.length, marked, spanMarked, settledDelta, listErr, sliceOk, inlineHits, srcHead: src.slice(0, 160) };
  }).catch((e) => ({ err: e.message }));
  console.log(`  direct settle call: ${JSON.stringify(direct)}`);
  const r = await p.evaluate(() => {
    const n = document.getElementById('wh-connection-notice');
    const cs = n ? getComputedStyle(n) : null; const rect = n ? n.getBoundingClientRect() : null;
    const PROG = /^(Computing|Loading|Counting|Reading|Rolling up|Fetching|Building)[^.]{0,90}(\.\.\.|…)\s*$/;
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null); const frozen = []; let node;
    while ((node = w.nextNode())) { const t = (node.textContent || '').trim(); if (t && PROG.test(t)) frozen.push(t.slice(0, 40) + ' <' + node.parentElement.tagName.toLowerCase() + (node.parentElement.checkVisibility() ? '' : ' hidden') + (node.parentElement.offsetParent === null ? ' noOffsetParent' : '') + '>'); }
    const chips = [...document.querySelectorAll('.wh-source-chip')].map((c) => (c.textContent || '').trim().slice(0, 50) + (c.offsetParent === null ? ' [noOffsetParent]' : '') + (c.checkVisibility() ? '' : ' [hidden]'));
    const failedTexts = [...document.querySelectorAll('.wh-list-error, [role="alert"], .honest-empty')].filter((e) => e.checkVisibility()).map((e) => (e.innerText || '').trim().slice(0, 60));
    return { noted: window._whConnNoted || 0, settled: window._whSettled ?? null, notice: n ? { pos: cs.position, disp: cs.display, offsetParent: n.offsetParent !== null, rect: [Math.round(rect.top), Math.round(rect.height)], text: (n.innerText || '').slice(0, 70), checkVis: n.checkVisibility() } : null, frozen, chips, failedTexts, skeletons: document.querySelectorAll('.wh-skeleton').length };
  });
  console.log(`== ${file}\n  notice: ${JSON.stringify(r.notice)}\n  _whConnNoted=${r.noted} settledPasses=${r.settled} skeletons=${r.skeletons}\n  frozen: ${JSON.stringify(r.frozen)}\n  chips: ${JSON.stringify(r.chips)}\n  failed texts: ${JSON.stringify(r.failedTexts)}\n  console: ${JSON.stringify(errs.slice(0, 4))}`);
  await p.close();
}
await b.close();
