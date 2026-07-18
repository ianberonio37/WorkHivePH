// state_probe.mjs — dump a page's end-state (which named panels are visible, main's text head,
// console errors) after the sweep sign-in. USAGE: node tools/state_probe.mjs ph-intelligence.html
import { chromium } from 'playwright';
const SEEDER = 'http://127.0.0.1:5000';
const EMAIL = 'pabloaguilar@auth.workhiveph.com', PASSWORD = 'test1234';
const HIVE = 'c9def338-fd73-4b19-8ef1-ee57625953d6', WORKER = 'Pablo Aguilar';
const file = process.argv[2];
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

const page = await context.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push('PAGEERROR: ' + String(e).slice(0, 200)));
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errs.push(m.type() + ': ' + m.text().slice(0, 160)); });
await page.goto(`${SEEDER}/workhive/${file}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(8000);
const state = await page.evaluate(() => {
  const vis = (id) => { const e = document.getElementById(id); if (!e) return 'ABSENT'; const s = getComputedStyle(e); return (s.display === 'none' || e.classList.contains('hidden') || e.offsetParent === null) ? 'hidden' : 'VISIBLE'; };
  const main = document.querySelector('main, .page');
  return {
    loading: vis('loading-state'), noReport: vis('no-report-state'), reportContent: vis('report-content'),
    maturityEmpty: !!document.querySelector('[data-maturity-empty], .maturity-empty, .honest-empty'),
    mainText: (main ? main.innerText : '').replace(/\s+/g, ' ').trim().slice(0, 220),
    fns: { checkMaturityGate: typeof window.checkMaturityGate, whListSkeleton: typeof window.whListSkeleton, renderMaturityHonestEmpty: typeof window.renderMaturityHonestEmpty },
  };
});
console.log(JSON.stringify(state, null, 1));
console.log('CONSOLE/ERRORS:', errs.slice(0, 12).join('\n  ') || 'none');
await page.close();
await browser.close();
