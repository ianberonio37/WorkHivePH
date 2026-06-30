// cls_attribution.mjs — Arc L · L1 diagnostic: WHICH elements drive the CLS.
//
// The L0 sweep proved CLS is the dominant Speed defect platform-wide, but
// `getEntriesByType('layout-shift')` drops the `sources` once the page settles
// (performance skill). This probe installs the layout-shift observer at
// DOCUMENT-START (via addInitScript, before any page script) and KEEPS the
// per-shift `sources` (the actual nodes that moved + their value), so we can
// target the real offenders with reserved-space fixes instead of guessing.
//
// USAGE:
//   node tools/cls_attribution.mjs                       # top-CLS pages
//   node tools/cls_attribution.mjs --page asset-hub.html
//   node tools/cls_attribution.mjs --all                 # all 36 user-facing

import { chromium } from 'playwright';
import { readFileSync } from 'fs';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const EMAIL = process.env.WH_TEST_EMAIL || 'leandromarquez@auth.workhiveph.com';
const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const HIVE = '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7';
const WORKER = process.env.WH_TEST_WORKER || 'Leandro Marquez';

const args = process.argv.slice(2);
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const ALL = args.includes('--all');

// the worst-CLS pages from the L0 baseline (perf_scale_results.json S findings)
const DEFAULT_PAGES = ['asset-hub.html', 'assistant.html', 'engineering-design.html',
  'audit-log.html', 'integrations.html', 'community.html', 'dayplanner.html',
  'hive.html', 'project-manager.html', 'status.html', 'predictive.html'];

// installed at document-start so it captures EVERY shift from first paint
const OBSERVER_SRC = `
  window.__CLS = { total: 0, shifts: [] };
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        if (e.hadRecentInput) continue;
        window.__CLS.total += e.value;
        const srcs = (e.sources || []).map(s => {
          const n = s.node;
          if (!n || n.nodeType !== 1) return { sel: '(text/anon)', v: e.value };
          const id = n.id ? '#' + n.id : '';
          const cls = (n.className && typeof n.className === 'string') ? '.' + n.className.trim().split(/\\s+/).slice(0, 2).join('.') : '';
          return { sel: n.tagName.toLowerCase() + id + cls, v: e.value };
        });
        window.__CLS.shifts.push({ value: e.value, t: Math.round(e.startTime), sources: srcs });
      }
    }).observe({ type: 'layout-shift', buffered: true });
  } catch (e) { window.__CLS.err = String(e); }
`;

async function signIn(context) {
  const page = await context.newPage();
  await page.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
  await page.evaluate(async ({ email, password, hive, worker }) => {
    try {
      const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
      await db.auth.signInWithPassword({ email, password });
      localStorage.setItem('wh_active_hive_id', hive);
      localStorage.setItem('wh_last_worker', worker);
    } catch (e) {}
  }, { email: EMAIL, password: PASSWORD, hive: HIVE, worker: WORKER });
  await page.close();
}

async function probe(context, pageFile) {
  const page = await context.newPage();
  await page.addInitScript(OBSERVER_SRC);
  try {
    await page.goto(`${SEEDER}/workhive/${pageFile}`, { waitUntil: 'load', timeout: 30000 });
    await page.waitForTimeout(3500); // let all async renders fire
    const cls = await page.evaluate(() => window.__CLS);
    await page.close();
    // aggregate shift value by source selector
    const bySel = {};
    for (const sh of cls.shifts) for (const s of sh.sources) bySel[s.sel] = (bySel[s.sel] || 0) + sh.value / sh.sources.length;
    const top = Object.entries(bySel).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([sel, v]) => ({ sel, v: Math.round(v * 1000) / 1000 }));
    return { total: Math.round(cls.total * 1000) / 1000, shiftCount: cls.shifts.length, top };
  } catch (e) {
    await page.close().catch(() => {});
    return { error: String(e).slice(0, 120) };
  }
}

(async () => {
  let pages = PAGE_ONLY ? [PAGE_ONLY] : DEFAULT_PAGES;
  if (ALL) {
    const r = JSON.parse(readFileSync('perf_scale_results.json', 'utf8'));
    pages = Object.keys(r.surfaces).filter(k => k.startsWith('page::')).map(k => k.replace('page::', ''));
  }
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 780 } });
  await signIn(context);
  console.log('CLS source attribution (top shifting elements per page):\n');
  for (const p of pages) {
    const r = await probe(context, p);
    if (r.error) { console.log(`${p.padEnd(34)} ERROR ${r.error}`); continue; }
    console.log(`${p}  CLS=${r.total}  (${r.shiftCount} shifts)`);
    for (const t of r.top) if (t.v > 0.005) console.log(`    ${String(t.v).padStart(6)}  ${t.sel}`);
  }
  await browser.close();
})();
