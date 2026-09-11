// probe_hive_settle_trace — run the settle's OWN source on hive with tracing injected (2026-09-05): what does vis() return for
// every PROG hit and every chip, and what does the Live test see?
import { chromium } from 'playwright';
import { SEEDER, signIn, SETTLE_MS } from './prover_harness.mjs';
const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
await signIn(ctx); const p = await ctx.newPage();
await p.route('**/*', (route) => /\/rest\/v1\/|\/functions\/v1\/|\/realtime\/v1\/|\/storage\/v1\//.test(route.request().url()) ? route.abort('failed') : route.continue());
await p.goto(`${SEEDER}/workhive/hive.html`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
await p.waitForTimeout(SETTLE_MS);
const r = await p.evaluate(() => {
  window.__dbg = { chips: [], hits: [], progSrc: null, visSrc: null };
  let src = _whSettleStuckLoaders.toString();
  src = src.replace("var chips = Array.prototype.slice.call(document.querySelectorAll('.wh-source-chip'));", "var chips = Array.prototype.slice.call(document.querySelectorAll('.wh-source-chip')); window.__dbg.visSrc = vis.toString();");
  src = src.replace("var c = chips[k]; if (!vis(c) ||", "var c = chips[k]; window.__dbg.chips.push({ t: (c.textContent||'').trim().slice(0,24), vis: vis(c), cv: c.checkVisibility(), flag: c.getAttribute('data-wh-read-failed'), live: /^Live/i.test((c.textContent||'').trim()) }); if (!vis(c) ||");
  src = src.replace("if (t && PROG.test(t) && node.parentElement && vis(node.parentElement)) hits.push(node);", "if (t && PROG.test(t)) { window.__dbg.hits.push({ t: t.slice(0,30), vis: node.parentElement ? vis(node.parentElement) : null, cv: node.parentElement ? node.parentElement.checkVisibility() : null }); } if (t && PROG.test(t) && node.parentElement && vis(node.parentElement)) hits.push(node);");
  src = src.replace("var walker = document.createTreeWalker", "window.__dbg.progSrc = PROG.toString(); var walker = document.createTreeWalker");
  const injected = (src.match(/__dbg/g) || []).length;
  let err = null; try { (0, eval)('(' + src + ')')(); } catch (e) { err = String(e && e.message); }
  return { injected, err, dbg: window.__dbg, marked: document.querySelectorAll('[data-wh-read-failed]').length, span: (document.getElementById('ss-verdict-label') || {}).textContent };
});
console.log(JSON.stringify(r, null, 1).slice(0, 3000));
await b.close();
