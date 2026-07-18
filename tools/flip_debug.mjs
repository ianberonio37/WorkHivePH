// flip_debug.mjs — dump each N1 labelEl's before/after text on a language flip. USAGE: node tools/flip_debug.mjs analytics.html
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
await page.goto(`${SEEDER}/workhive/${file}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(5000);
const out = await page.evaluate(async () => {
  const R = document.querySelector('.page') || document.querySelector('main') || document.body;
  const sel = 'h1, h2, h3, button, label, [class*="section-label"]';
  const vis = (e) => e && e.offsetParent !== null && (e.textContent || '').trim().length > 2 && e.getAttribute('translate') !== 'no' && !e.classList.contains('card-title') && !e.closest('.card-title');
  const els = [...R.querySelectorAll(sel)].filter(vis);
  const before = els.map((e) => ({ tag: e.tagName, di: e.hasAttribute('data-i') || !!e.querySelector('[data-i]'), t: (e.textContent || '').trim().slice(0, 40) }));
  const orig = window.WH_LANG === 'fil' ? 'fil' : 'en';
  window.setLang(orig === 'fil' ? 'en' : 'fil');
  await new Promise((r) => setTimeout(r, 1500));
  const after = [...R.querySelectorAll(sel)].filter(vis).map((e) => (e.textContent || '').trim().slice(0, 40));
  window.setLang(orig);
  return before.map((b, i) => ({ ...b, after: after[i] || '(none)', changed: after[i] && b.t !== after[i] }));
});
console.log(`total labels: ${out.length} · changed: ${out.filter((o) => o.changed).length}`);
out.forEach((o) => console.log(`  ${o.changed ? 'Y' : 'n'} ${o.di ? 'di' : '  '} ${o.tag.padEnd(6)} "${o.t}"  ->  "${o.after}"`));
await page.close();
await browser.close();
