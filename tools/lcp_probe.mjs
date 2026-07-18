// lcp_probe.mjs — WHY is LCP late? Captures each LCP candidate as it fires (element, size, startTime),
// plus the slowest resources, so we can see whether LCP waits on a DB render, a font, or a big image.
// Reuses the family sweep sign-in. USAGE: node tools/lcp_probe.mjs community.html assistant.html
import { chromium } from 'playwright';
const SEEDER = 'http://127.0.0.1:5000';
const EMAIL = 'pabloaguilar@auth.workhiveph.com', PASSWORD = 'test1234';
const HIVE = 'c9def338-fd73-4b19-8ef1-ee57625953d6', WORKER = 'Pablo Aguilar';
const pages = process.argv.slice(2);

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const s = await context.newPage();
await s.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await s.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
await s.evaluate(async ({ email, password, hive, worker }) => {
  try { const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
    await db.auth.signInWithPassword({ email, password });
    localStorage.setItem('wh_active_hive_id', hive); localStorage.setItem('wh_last_worker', worker); localStorage.setItem('wh_hive_role', 'supervisor');
  } catch (e) {} }, { email: EMAIL, password: PASSWORD, hive: HIVE, worker: WORKER });
await s.close();

for (const file of pages) {
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.__lcps = [];
    const desc = (n) => { try { return n && n.nodeType === 1 ? (n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') + (typeof n.className === 'string' && n.className ? '.' + n.className.trim().split(/\s+/).slice(0, 2).join('.') : '')) : String(n); } catch (e) { return '?'; } };
    new PerformanceObserver((l) => { for (const e of l.getEntries()) {
      window.__lcps.push({ t: Math.round(e.startTime), size: Math.round(e.size), node: desc(e.element), txt: (e.element?.textContent || '').trim().slice(0, 40) });
    } }).observe({ type: 'largest-contentful-paint', buffered: true });
  });
  const t0 = Date.now();
  await page.goto(`${SEEDER}/workhive/${file}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(6500);
  const lcps = await page.evaluate(() => window.__lcps || []);
  const res = await page.evaluate(() => performance.getEntriesByType('resource')
    .map(r => ({ n: r.name.split('/').pop().slice(0, 40), end: Math.round(r.responseEnd), dur: Math.round(r.duration) }))
    .sort((a, b) => b.end - a.end).slice(0, 6));
  const nav = await page.evaluate(() => { const n = performance.getEntriesByType('navigation')[0] || {}; return { dcl: Math.round(n.domContentLoadedEventEnd || 0), load: Math.round(n.loadEventEnd || 0) }; });
  console.log(`\n=== ${file} === nav DCL=${nav.dcl}ms load=${nav.load}ms`);
  console.log('  LCP candidates (t · size · node · text):');
  lcps.forEach(l => console.log(`    ${String(l.t).padEnd(6)} size=${String(l.size).padEnd(7)} ${l.node.padEnd(30)} "${l.txt}"`));
  console.log(`  FINAL LCP = ${lcps.length ? lcps[lcps.length - 1].t : '?'}ms`);
  console.log('  Slowest resources (responseEnd · dur · name):');
  res.forEach(r => console.log(`    ${String(r.end).padEnd(6)} ${String(r.dur).padEnd(6)} ${r.n}`));
  await page.close();
}
await browser.close();
