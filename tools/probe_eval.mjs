// probe_eval — sign in as the harness worker, open ONE page, wait the settle, evaluate a JS expression, print JSON.
//   node tools/probe_eval.mjs hive.html "document.querySelectorAll('button').length" [--settle 6000]
import { chromium } from 'playwright';
import { SEEDER, signIn, PAGE_QUERY, SETTLE_MS } from './prover_harness.mjs';
const [file, js] = process.argv.slice(2);
const si = process.argv.indexOf('--settle'); const settle = si >= 0 ? Number(process.argv[si + 1]) : SETTLE_MS;
const PHONE = process.argv.includes('--phone');   // 390x844 touch phone (the phone-fit lens's device)
const vwi = process.argv.indexOf('--vw'); const VW = vwi >= 0 ? Number(process.argv[vwi + 1]) : 1280;   // --vw 1920 = the family sweep's own viewport
const b = await chromium.launch(); const ctx = await b.newContext(PHONE ? { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, serviceWorkers: 'block' } : { viewport: { width: VW, height: VW >= 1600 ? 1080 : 800 }, serviceWorkers: 'block' }); const asi = process.argv.indexOf('--as');   // --as pablo = the family sweep's own actor (a different hive, a different card set)
const ACTORS = { pablo: { name: 'Pablo Aguilar', first: 'Pablo', email: 'pabloaguilar@auth.workhiveph.com', password: 'test1234' } };
await signIn(ctx, asi >= 0 ? (ACTORS[process.argv[asi + 1]] || {}) : {});
const p = await ctx.newPage();
// --cls: install a layout-shift observer at DOCUMENT START; window.__cls then lists every shift with its sources + rects
if (process.argv.includes('--cls')) await p.addInitScript(() => { window.__cls = []; new PerformanceObserver((l) => { for (const e of l.getEntries()) { if (e.hadRecentInput) continue; window.__cls.push({ t: Math.round(e.startTime), v: +e.value.toFixed(4), src: (e.sources || []).map((s) => { const n = s.node; const nm = n ? (n.id ? '#' + n.id : (n.tagName || n.nodeName || '').toLowerCase() + (n.className && typeof n.className === 'string' ? '.' + n.className.split(' ')[0] : '')) : '?'; const pr = s.previousRect, cr = s.currentRect; return `${nm} ${pr.x},${pr.y} ${pr.width}x${pr.height} -> ${cr.x},${cr.y} ${cr.width}x${cr.height}`; }) }); } }).observe({ type: 'layout-shift', buffered: true }); }); const errs = []; p.on('pageerror', (e) => errs.push(String(e).slice(0, 160)));
await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
await p.waitForTimeout(settle);
if (process.argv.includes('--rubric')) await p.evaluate((src) => { eval('(' + src + ')')(); }, (await import('fs')).readFileSync('survey_ufai_rubric.js', 'utf8'));   // the rubric is a bare function expression, invoked the way family_rubric_sweep does; window.__RUBRIC.survey({ pageId }) then available
const ci = process.argv.indexOf('--click'); if (ci >= 0) for (const sel of process.argv[ci + 1].split(',')) { await (PHONE ? p.tap(sel, { timeout: 4000, force: true }) : p.click(sel, { timeout: 4000, force: true })).catch((e) => console.log('click failed', sel, String(e).slice(0, 80))); await p.waitForTimeout(700); }
const shi = process.argv.indexOf('--shot'); if (shi >= 0) { await p.screenshot({ path: process.argv[shi + 1], fullPage: true }); console.log('shot:', process.argv[shi + 1]); }   // full-page screenshot (the whole-artifact discipline)
const r = js ? await p.evaluate(js).catch((e) => ({ evalError: String(e).slice(0, 300) })) : null;
console.log(JSON.stringify(r, null, 1).slice(0, 6000)); if (errs.length) console.log('pageErrors:', errs);
await b.close();
