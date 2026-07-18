// r1_gap_diagnostic.mjs — pinpoint R1 off-grid TOP-LEVEL gaps + their culprit element.
// R1 (survey_ufai_rubric.js) measures the VERTICAL gap between the root's DIRECT children;
// a gap not on the 8-pt grid {0,4,8,12,16,24,32}/%8 fails. The board note lists the values
// but not WHICH pair produces them. This reuses family_rubric_sweep's sign-in (pabloaguilar
// supervisor, same origin) and dumps, per page: each off-grid gap, the two blocks, and the
// margins that make it — so the fix is a targeted margin edit, not a blind grep.
//
// USAGE: node tools/r1_gap_diagnostic.mjs analytics.html inventory.html ...
import { chromium } from 'playwright';

const SEEDER = 'http://127.0.0.1:5000';
const EMAIL = 'pabloaguilar@auth.workhiveph.com', PASSWORD = 'test1234';
const HIVE = 'c9def338-fd73-4b19-8ef1-ee57625953d6', WORKER = 'Pablo Aguilar';
const pages = process.argv.slice(2);

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });

// sign in once (same recipe as the sweep)
const s = await context.newPage();
await s.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await s.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
await s.evaluate(async ({ email, password, hive, worker }) => {
  try {
    const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
    await db.auth.signInWithPassword({ email, password });
    localStorage.setItem('wh_active_hive_id', hive);
    localStorage.setItem('wh_last_worker', worker);
    localStorage.setItem('wh_hive_role', 'supervisor');
  } catch (e) { /* ignore */ }
}, { email: EMAIL, password: PASSWORD, hive: HIVE, worker: WORKER });
await s.close();

for (const file of pages) {
  const page = await context.newPage();
  await page.goto(`${SEEDER}/workhive/${file}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3200);
  const rows = await page.evaluate(() => {
    const vis = (e) => { if (!e || e.offsetParent === null) return false; const s = getComputedStyle(e); return s.display !== 'none' && s.visibility !== 'hidden'; };
    const cands = ['.page', '#ar-print-wrapper', '#ar-page', 'main'].map((sel) => document.querySelector(sel)).filter((el) => el && el.children.length > 0);
    const weigh = (el) => (el.innerText || '').trim().length + el.querySelectorAll('h1,h2,h3,table,.card,.simple-card').length * 40;
    const R = cands.length ? cands.reduce((b, e) => (weigh(e) > weigh(b) ? e : b), cands[0]) : document.body;
    const kids = [...R.children].filter(vis);
    const grid = (g) => [0, 4, 8, 12, 16, 24, 32].includes(g) || g % 8 === 0;
    const out = [];
    for (let i = 1; i < kids.length; i++) {
      const p = kids[i - 1].getBoundingClientRect(), c = kids[i].getBoundingClientRect();
      const g = Math.round(c.top - p.bottom);
      if (g >= 0 && !grid(g)) {
        const tag = (e) => e.tagName + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/)[0] : '');
        out.push({ gap: g, prev: tag(kids[i - 1]), prevMb: getComputedStyle(kids[i - 1]).marginBottom, next: tag(kids[i]), nextMt: getComputedStyle(kids[i]).marginTop });
      }
    }
    return out;
  });
  console.log(`\n=== ${file} ===`);
  if (!rows.length) console.log('  (no off-grid top-level gaps — R1 clean in this state)');
  for (const r of rows) console.log(`  gap=${r.gap}px  [${r.prev} mb=${r.prevMb}] -> [${r.next} mt=${r.nextMt}]`);
  await page.close();
}
await browser.close();
