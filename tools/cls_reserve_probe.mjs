// cls_reserve_probe.mjs — Arc L · L1 diagnostic: MEASURE the exact growth (h0→h1)
// of every above-the-fold container so reserved-space fixes are MEASURED, not guessed.
//
// cls_attribution.mjs tells us WHICH elements shift; this tells us BY HOW MUCH each
// async-filled container GROWS (height at first-paint vs settled), so the reserve
// (min-height) we add equals the real delta — the discipline the Arc L roadmap demands
// ("every reserve was measured 893px/161px, not guessed").
//
// For each page it snapshots, at T0 (right after `load`, before async DB fills) and at
// T1 (after a 3.5 s settle), the offsetHeight of:
//   - every element carrying an id (keyed by #id — stable across snapshots)
//   - the recurring command-center containers (.simple-row/.action-card/.verdict/.card/.feed/…)
// then reports the top GROWERS (h1 − h0 > 6px) per page = the reserve targets.
//
// USAGE:
//   node tools/cls_reserve_probe.mjs                       # the top-CLS cluster
//   node tools/cls_reserve_probe.mjs --page hive.html
//   node tools/cls_reserve_probe.mjs --all

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

const DEFAULT_PAGES = ['audit-log.html', 'integrations.html', 'community.html',
  'agentic-rag-observability.html', 'hive.html', 'project-manager.html',
  'status.html', 'predictive.html'];

// snapshot helper, evaluated in-page. Returns { '#id|.cls': height } for the
// above-fold container set. Keyed by a STABLE selector so T0/T1 diff lines up.
const SNAP_FN = `(() => {
  const out = {};
  const add = (sel, el) => { if (el && el.offsetParent !== null || (el && el.offsetHeight)) out[sel] = el.offsetHeight; };
  // every id'd element (stable key)
  for (const el of document.querySelectorAll('[id]')) {
    if (el.id) out['#' + el.id] = el.offsetHeight;
  }
  // recurring command-center containers (first instance only — they anchor the stack)
  for (const c of ['simple-row','action-card','verdict','filter-row','feed','presence-bar','layout-grid','slo','card','tbl','recent-row','tab-strip']) {
    const el = document.querySelector('.' + c);
    if (el) out['.' + c] = el.offsetHeight;
  }
  return out;
})()`;

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
  try {
    await page.goto(`${SEEDER}/workhive/${pageFile}`, { waitUntil: 'load', timeout: 30000 });
    const t0 = await page.evaluate(SNAP_FN);          // first paint, pre async-fill
    await page.waitForTimeout(3500);                  // let all async renders fire
    const t1 = await page.evaluate(SNAP_FN);          // settled
    await page.close();
    const grew = [];
    for (const sel of Object.keys(t1)) {
      const h0 = t0[sel] || 0, h1 = t1[sel];
      const d = h1 - h0;
      if (d > 6) grew.push({ sel, h0, h1, d });        // grew by >6px = a reserve target
    }
    grew.sort((a, b) => b.d - a.d);
    return { grew: grew.slice(0, 12) };
  } catch (e) {
    await page.close().catch(() => {});
    return { error: String(e).slice(0, 140) };
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
  console.log('CLS reserve targets — container growth h0(first-paint) → h1(settled), Δpx:\n');
  for (const p of pages) {
    const r = await probe(context, p);
    if (r.error) { console.log(`${p.padEnd(34)} ERROR ${r.error}`); continue; }
    console.log(`${p}`);
    for (const g of r.grew) console.log(`    Δ${String(g.d).padStart(5)}px   ${g.sel.padEnd(34)} (${g.h0}→${g.h1})`);
    if (!r.grew.length) console.log('    (no container grew >6px)');
    console.log('');
  }
  await browser.close();
})();
