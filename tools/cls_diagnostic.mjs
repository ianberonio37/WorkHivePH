// cls_diagnostic.mjs — find the EXACT elements causing CLS + what pushed them. The family sweep's
// I1 probe names only the biggest SHIFTER (e.g. div#wh-logbook-grid); it doesn't say what GREW to
// push it. This installs a detailed layout-shift observer BEFORE navigation (addInitScript) and
// logs every shift's node + previousRect.y → currentRect.y, so the real cause (an async element
// above the shifter that changed height) is visible. Reuses the family sweep sign-in.
// USAGE: node tools/cls_diagnostic.mjs logbook.html inventory.html
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
    window.__shifts = [];
    const desc = (n) => { try { return n && n.nodeType === 1 ? (n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') + (typeof n.className === 'string' && n.className ? '.' + n.className.trim().split(/\s+/).slice(0, 2).join('.') : '')) : String(n); } catch (e) { return '?'; } };
    new PerformanceObserver((l) => { for (const e of l.getEntries()) {
      if (e.hadRecentInput) continue;
      (e.sources || []).forEach((src) => {
        window.__shifts.push({ v: +e.value.toFixed(4), node: desc(src.node), fromY: Math.round(src.previousRect?.y ?? 0), toY: Math.round(src.currentRect?.y ?? 0), dH: Math.round((src.currentRect?.height ?? 0) - (src.previousRect?.height ?? 0)) });
      });
    } }).observe({ type: 'layout-shift', buffered: true });
  });
  await page.goto(`${SEEDER}/workhive/${file}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  // Time-series: sample the first-main-child heights + the biggest shifter's top over the load,
  // so a GROWING element (the real pusher) is unambiguous.
  const series = [];
  for (let i = 0; i < 14; i++) {
    const snap = await page.evaluate(() => {
      const main = document.querySelector('main, .page'); const kids = main ? [...main.children].slice(0, 4) : [];
      const tag = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/)[0] : '');
      return kids.map((k) => `${tag(k)}=${Math.round(k.getBoundingClientRect().height)}`).join('  ');
    }).catch(() => '');
    series.push(`  t=${(i * 450)}ms  ${snap}`);
    await page.waitForTimeout(450);
  }
  const shifts = await page.evaluate(() => (window.__shifts || []).sort((a, b) => b.v - a.v).slice(0, 12));
  console.log(`\n--- ${file} first-main-children height over load ---`);
  console.log(series.filter((s, i) => i === 0 || i === 3 || i === 6 || i === 13).join('\n'));
  console.log(`\n=== ${file} — top layout shifts (node · Δy · Δheight · value) ===`);
  shifts.forEach((sh) => console.log(`  ${String(sh.v).padEnd(7)} ${sh.node.padEnd(34)} y:${sh.fromY}→${sh.toY}  ΔH:${sh.dH}`));
  await page.close();
}
await browser.close();
