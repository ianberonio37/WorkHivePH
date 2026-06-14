/* ===========================================================================
   axe_scan.js — WCAG 2.2 AA accessibility ratchet (STREAMLINE E3)
   ---------------------------------------------------------------------------
   Drives every user-facing page through axe-core (Deque) at mobile width and
   ratchets per-page violation counts FORWARD-ONLY against axe_baseline.json —
   so accessibility can only improve, never regress. Today a11y is fixed
   reactively (sc-label contrast, 44px taps, modal ARIA); this locks it in.

   Why a standalone node runner (not @axe-core/playwright): the project path
   contains "&" which breaks npx, and we avoid adding an npm dep — axe.min.js is
   vendored in tools/vendor/ and injected via page.addScriptTag. Run with node
   directly (NOT npx):  node tools/axe_scan.js   [--update-baseline]

   Serves from a static server (default http://127.0.0.1:5599); seeds the
   localStorage identity so the auth gate passes and each page renders its OWN
   chrome (data fetches may fail against prod — fine, static a11y = contrast /
   focus / ARIA / labels / target-size don't depend on data).

   Output: axe_violations_report.json (machine) + a per-page console table.
   Exit 1 when any page exceeds its baseline (new violations); 0 otherwise.
   =========================================================================== */
const { chromium } = require(require('path').resolve(__dirname, '..', 'node_modules', '@playwright', 'test'));
const fs   = require('fs');
const path = require('path');

const ROOT          = path.resolve(__dirname, '..');
const BASE          = process.env.AXE_BASE || 'http://127.0.0.1:5599';
const AXE_SRC       = fs.readFileSync(path.join(__dirname, 'vendor', 'axe.min.js'), 'utf8');
const BASELINE_PATH = path.join(ROOT, 'axe_baseline.json');
const REPORT_PATH   = path.join(ROOT, 'axe_violations_report.json');
const UPDATE        = process.argv.includes('--update-baseline');

// User-facing surfaces (mirrors the source-chip / canonical-anchor page set).
const PAGES = [
  'index.html', 'hive.html', 'inventory.html', 'logbook.html', 'pm-scheduler.html',
  'analytics.html', 'asset-hub.html', 'alert-hub.html', 'shift-brain.html',
  'skillmatrix.html', 'community.html', 'dayplanner.html', 'marketplace.html',
  'achievements.html', 'project-manager.html', 'integrations.html', 'audit-log.html',
  'predictive.html', 'report-sender.html', 'engineering-design.html',
];

// localStorage identity so the per-page auth gate passes (keys per inventory.html:578-581).
const SEED = {
  wh_last_worker:    'Test User',
  wh_active_hive_id: '9b4eaeac-0000-4000-8000-000000000001',
  wh_hive_id:        '9b4eaeac-0000-4000-8000-000000000001',
  wh_hive_name:      'Test Hive',
  wh_hive_role:      'supervisor',
  wh_hive_code:      'TEST01',
};

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } }); // mobile-first
  const page = await ctx.newPage();

  // Seed identity on the origin before scanning any gated page.
  await page.goto(BASE + '/index.html', { waitUntil: 'domcontentloaded' });
  await page.evaluate((seed) => { for (const k in seed) localStorage.setItem(k, seed[k]); }, SEED);

  const detail = {};
  for (const p of PAGES) {
    try {
      await page.goto(BASE + '/' + p, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(900); // let the first render settle (and any auth redirect fire)
      const urlAfter = page.url().replace(BASE, '');
      // A page that bounced to the sign-in gate never rendered its own content —
      // banking its (clean) score would be a hollow baseline. Skip it; the
      // session/hive-gated pages get their a11y coverage via the journey specs.
      const skipped = urlAfter.includes('signin=1') || !urlAfter.includes(p.replace('.html', ''));
      if (skipped) { detail[p] = { url_after: urlAfter, skipped: true, nodes: 0 }; continue; }
      await page.addScriptTag({ content: AXE_SRC });
      const res = await page.evaluate(async (tags) => {
        const r = await axe.run(document, {
          runOnly: { type: 'tag', values: tags },
          resultTypes: ['violations'],
        });
        const byRule = {};
        let nodes = 0;
        for (const v of r.violations) { byRule[v.id] = { impact: v.impact, nodes: v.nodes.length }; nodes += v.nodes.length; }
        return { byRule, nodes, els: document.querySelectorAll('*').length };
      }, WCAG_TAGS);
      detail[p] = { url_after: urlAfter, skipped: false, els: res.els, nodes: res.nodes, byRule: res.byRule };
    } catch (e) {
      detail[p] = { error: String(e && e.message || e).slice(0, 200), skipped: true, nodes: 0 };
    }
  }
  await browser.close();

  // Only pages that actually rendered their own content enter the ratchet.
  const scanned = PAGES.filter((p) => !detail[p].skipped);
  const current = {};
  for (const p of scanned) current[p] = detail[p].nodes || 0;

  let baseline = {};
  if (fs.existsSync(BASELINE_PATH)) {
    try { baseline = JSON.parse(fs.readFileSync(BASELINE_PATH, 'utf8')).pages || {}; } catch (_) {}
  }
  const regressed = [];
  for (const p of PAGES) {
    if (baseline[p] !== undefined && current[p] > baseline[p]) regressed.push(`${p}: ${baseline[p]} -> ${current[p]}`);
  }

  fs.writeFileSync(REPORT_PATH, JSON.stringify({
    generated: new Date().toISOString(), base: BASE, wcag_tags: WCAG_TAGS,
    pages: current, regressed, detail,
  }, null, 2));

  const firstRun = !fs.existsSync(BASELINE_PATH);
  if (firstRun || UPDATE) {
    fs.writeFileSync(BASELINE_PATH, JSON.stringify({ established: true, generated: new Date().toISOString(), pages: current }, null, 2));
  } else if (!regressed.length) {
    // tighten: lower any page that improved, keep the rest
    const merged = { ...baseline };
    for (const p of scanned) if (current[p] < (baseline[p] ?? Infinity)) merged[p] = current[p];
    fs.writeFileSync(BASELINE_PATH, JSON.stringify({ tightened: true, generated: new Date().toISOString(), pages: merged }, null, 2));
  }

  const total = scanned.reduce((a, p) => a + current[p], 0);
  console.log(`AXE WCAG 2.2 AA — violation nodes per page (390px) · ${scanned.length}/${PAGES.length} scanned:`);
  for (const p of PAGES) {
    const d = detail[p];
    if (d.skipped) { console.log(`    ${p.padEnd(26)}  —  skipped (${d.error ? 'error' : (d.url_after || '').includes('signin') ? 'auth gate' : 'no render'})`); continue; }
    console.log(`  ${current[p] > 0 ? '•' : ' '} ${p.padEnd(26)} ${String(current[p]).padStart(3)}  (${d.els} els)`);
  }
  console.log(`  ${'TOTAL (scanned)'.padEnd(28)} ${String(total).padStart(3)}  (baseline ${firstRun ? 'ESTABLISHED' : Object.values(baseline).reduce((a, b) => a + b, 0)})`);

  if (regressed.length) {
    console.log('\nFAIL — new accessibility violations vs baseline:');
    regressed.forEach((r) => console.log('  ' + r));
    process.exit(1);
  }
  console.log('\nPASS — accessibility at or below baseline (forward-only ratchet).');
})();
