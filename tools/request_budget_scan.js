/* ===========================================================================
   request_budget_scan.js — per-page data-request budget ratchet (STREAMLINE E7)
   ---------------------------------------------------------------------------
   Loads every user-facing page through a real browser and counts the Supabase
   DATA requests it fires on load (`/rest/v1/...` table reads + `/rest/v1/rpc/...`
   + `/functions/v1/...` edge fns), then ratchets the per-page count FORWARD-ONLY
   against request_budget_baseline.json — so query fan-out can only shrink, never
   grow. hive.html historically fired ~37 REST calls/load; the get_hive_board_
   dashboard RPC collapse brought that down, and this gate stops it creeping back.

   Same harness as tools/axe_scan.js (node + the installed Playwright, NOT npx;
   seeds the localStorage identity; skips pages that bounce to ?signin=1 so a
   redirected page never banks a hollow low count). The requests COUNT even when
   they 401/404 against prod — fan-out is about how many calls fire, not success.

   Run:  node tools/request_budget_scan.js   [--update-baseline]
   Out:  request_budget_report.json + a per-page console table. Exit 1 on any
   page exceeding its baseline; 0 otherwise.
   =========================================================================== */
const { chromium } = require(require('path').resolve(__dirname, '..', 'node_modules', '@playwright', 'test'));
const fs   = require('fs');
const path = require('path');

const ROOT          = path.resolve(__dirname, '..');
const BASE          = process.env.AXE_BASE || 'http://127.0.0.1:5599';
const BASELINE_PATH = path.join(ROOT, 'request_budget_baseline.json');
const REPORT_PATH   = path.join(ROOT, 'request_budget_report.json');
const UPDATE        = process.argv.includes('--update-baseline');

const PAGES = [
  'index.html', 'hive.html', 'inventory.html', 'logbook.html', 'pm-scheduler.html',
  'analytics.html', 'asset-hub.html', 'alert-hub.html', 'shift-brain.html',
  'skillmatrix.html', 'community.html', 'dayplanner.html', 'marketplace.html',
  'achievements.html', 'project-manager.html', 'integrations.html', 'audit-log.html',
  'predictive.html', 'report-sender.html', 'engineering-design.html',
];

const SEED = {
  wh_last_worker:    'Test User',
  wh_active_hive_id: '9b4eaeac-0000-4000-8000-000000000001',
  wh_hive_id:        '9b4eaeac-0000-4000-8000-000000000001',
  wh_hive_name:      'Test Hive',
  wh_hive_role:      'supervisor',
  wh_hive_code:      'TEST01',
};

const DATA_RE = /\/rest\/v1\/|\/functions\/v1\/|\/rpc\//;

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();

  await page.goto(BASE + '/index.html', { waitUntil: 'domcontentloaded' });
  await page.evaluate((seed) => { for (const k in seed) localStorage.setItem(k, seed[k]); }, SEED);

  const detail = {};
  for (const p of PAGES) {
    let reqs = [];
    const onReq = (r) => { const u = r.url(); if (DATA_RE.test(u)) reqs.push(u.replace(/\?.*$/, '').replace(/https?:\/\/[^/]+/, '')); };
    page.on('request', onReq);
    try {
      await page.goto(BASE + '/' + p, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1500); // let load-time fan-out settle
      const urlAfter = page.url().replace(BASE, '');
      const skipped = urlAfter.includes('signin=1') || !urlAfter.includes(p.replace('.html', ''));
      // tally distinct endpoints + total calls (rpc/table fan-out)
      const endpoints = {};
      for (const u of reqs) endpoints[u] = (endpoints[u] || 0) + 1;
      detail[p] = skipped
        ? { skipped: true, url_after: urlAfter, count: 0 }
        : { skipped: false, count: reqs.length, distinct: Object.keys(endpoints).length, top: Object.entries(endpoints).sort((a, b) => b[1] - a[1]).slice(0, 6) };
    } catch (e) {
      detail[p] = { skipped: true, error: String(e && e.message || e).slice(0, 160), count: 0 };
    }
    page.off('request', onReq);
  }
  await browser.close();

  const scanned = PAGES.filter((p) => !detail[p].skipped);
  const current = {};
  for (const p of scanned) current[p] = detail[p].count;

  let baseline = {};
  if (fs.existsSync(BASELINE_PATH)) {
    try { baseline = JSON.parse(fs.readFileSync(BASELINE_PATH, 'utf8')).pages || {}; } catch (_) {}
  }
  const regressed = [];
  for (const p of scanned) {
    if (baseline[p] !== undefined && current[p] > baseline[p]) regressed.push(`${p}: ${baseline[p]} -> ${current[p]}`);
  }

  fs.writeFileSync(REPORT_PATH, JSON.stringify({ generated: new Date().toISOString(), base: BASE, pages: current, regressed, detail }, null, 2));

  const firstRun = !fs.existsSync(BASELINE_PATH);
  if (firstRun || UPDATE) {
    fs.writeFileSync(BASELINE_PATH, JSON.stringify({ established: true, generated: new Date().toISOString(), pages: current }, null, 2));
  } else if (!regressed.length) {
    const merged = { ...baseline };
    for (const p of scanned) if (current[p] < (baseline[p] ?? Infinity)) merged[p] = current[p];
    fs.writeFileSync(BASELINE_PATH, JSON.stringify({ tightened: true, generated: new Date().toISOString(), pages: merged }, null, 2));
  }

  console.log(`Per-page DATA-request budget (REST + RPC + edge fns) · ${scanned.length}/${PAGES.length} scanned:`);
  for (const p of PAGES) {
    const d = detail[p];
    if (d.skipped) { console.log(`    ${p.padEnd(26)}  —  skipped`); continue; }
    console.log(`  ${d.count >= 20 ? '⚠' : ' '} ${p.padEnd(26)} ${String(d.count).padStart(3)} calls (${d.distinct} endpoints)`);
  }
  console.log(`  baseline ${firstRun ? 'ESTABLISHED' : 'tracked'}.`);
  if (regressed.length) {
    console.log('\nFAIL — query fan-out grew vs baseline:');
    regressed.forEach((r) => console.log('  ' + r));
    process.exit(1);
  }
  console.log('\nPASS — per-page request count at or below baseline (forward-only).');
})();
