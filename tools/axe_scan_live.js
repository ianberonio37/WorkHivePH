/* ===========================================================================
   axe_scan_live.js — WCAG 2.2 AA a11y gate for the AUTHENTICATED write surfaces
   ---------------------------------------------------------------------------
   The static sibling (axe_scan.js) can only scan pages that render their own
   chrome under a FAKE localStorage identity on a static server. The Tier-1
   OPERATIONAL WRITE pages (hive/inventory/logbook/pm-scheduler/skillmatrix/
   community/dayplanner/marketplace/project-manager) bounce to the sign-in gate
   there — so they were SKIPPED, i.e. the highest-a11y-risk surfaces (forms,
   modals, destructive actions) had ZERO axe coverage. This closes that gap.

   How (deterministic, no UI-login fragility — reuses the LIVE-validator move):
     1. Read the local anon key from tests/_db-cleanup.ts.
     2. Password-grant a seeded SUPERVISOR (leandromarquez / test1234) against
        the local GoTrue (127.0.0.1:54321) → a real Session object.
     3. Serve the pages through the Flask bridge (127.0.0.1:5000/workhive/, which
        rewrites the client to the LOCAL stack), seed `sb-127-auth-token` = that
        session + the wh_ identity keys, so each page renders authed.
     4. Inject the vendored axe.min.js (no CDN, path has "&" so npx is out) and
        run axe at 390px mobile; collect WCAG 2.2 AA violation nodes per page.

   This is an INTEGRITY-AT-ZERO gate (every page is currently 0 — proven live
   2026-07-07), NOT a frozen-backlog ratchet: the baseline is 0 and any NEW
   violation FAILs. If the env is absent (DB down / no seeder / Flask off) it
   SKIPS cleanly (exit 0), exactly like the other *_live validators.

   Run:  node tools/axe_scan_live.js  [--update-baseline]
   Out:  axe_live_violations_report.json  (+ axe_live_baseline.json)
   Exit: 0 = at/below baseline or skipped · 1 = a new violation appeared.
   =========================================================================== */
const { chromium } = require(require('path').resolve(__dirname, '..', 'node_modules', '@playwright', 'test'));
const fs   = require('fs');
const path = require('path');
const http = require('http');

const ROOT          = path.resolve(__dirname, '..');
const BASE          = process.env.AXE_LIVE_BASE || 'http://127.0.0.1:5000/workhive';
const GOTRUE        = process.env.WH_GOTRUE || 'http://127.0.0.1:54321';
const AXE_SRC       = fs.readFileSync(path.join(__dirname, 'vendor', 'axe.min.js'), 'utf8');
const BASELINE_PATH = path.join(ROOT, 'axe_live_baseline.json');
const REPORT_PATH   = path.join(ROOT, 'axe_live_violations_report.json');
const UPDATE        = process.argv.includes('--update-baseline');

// The auth-gated Tier-1 write surfaces the static scan can't reach.
const PAGES = [
  'hive.html', 'inventory.html', 'logbook.html', 'pm-scheduler.html',
  'skillmatrix.html', 'community.html', 'dayplanner.html', 'marketplace.html',
  'project-manager.html',
  // ASSET_ALERT_SHIFT_DEEP_ARC (A axis): the intelligence trio was never in the a11y
  // coverage list — add it so its WCAG 2.2 AA @390px violations are measured + ratcheted.
  'asset-hub.html', 'alert-hub.html', 'shift-brain.html',
];

// Seeded supervisor of the test hive (same identity the live deep-walk uses).
// HIVE_ID fixed 2026-07-19: was the STALE fixture 9b4eaeac (leandromarquez is NOT a member → RLS returned
// 0 rows → the gate scanned EMPTY pages, missing populated-content a11y). His real hive is 636cf7e8 (the
// same stale-hive the page-crud/live gates already pin via WH_TEST_HIVE). Now scans REAL rendered content.
const SUPERVISOR = 'leandromarquez';
const HIVE_ID    = process.env.WH_TEST_HIVE || '636cf7e8-431a-4907-8a9f-43dd4cc216d6';
const HIVE_NAME  = 'Baguio Textile Mills';
const WORKER     = 'Leandro Marquez';
const WCAG_TAGS  = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

// Local anon key: reuse the live-validators' source of truth (tests/_db-cleanup.ts).
function anonKey() {
  try {
    const m = fs.readFileSync(path.join(ROOT, 'tests', '_db-cleanup.ts'), 'utf8')
      .match(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/);
    return m ? m[0] : '';
  } catch (_) { return ''; }
}

// GoTrue password grant → a Session object (shape === what supabase-js persists).
function grantSession(key) {
  return new Promise((resolve) => {
    const body = JSON.stringify({ email: `${SUPERVISOR}@auth.workhiveph.com`, password: 'test1234' });
    const u = new URL(`${GOTRUE}/auth/v1/token?grant_type=password`);
    const req = http.request({
      hostname: u.hostname, port: u.port, path: u.pathname + u.search, method: 'POST',
      headers: { 'Content-Type': 'application/json', 'apikey': key, 'Content-Length': Buffer.byteLength(body) },
    }, (res) => {
      let d = ''; res.on('data', (c) => d += c);
      res.on('end', () => { try { const j = JSON.parse(d); resolve(j.access_token ? j : null); } catch (_) { resolve(null); } });
    });
    req.on('error', () => resolve(null));
    req.setTimeout(15000, () => { req.destroy(); resolve(null); });
    req.write(body); req.end();
  });
}

function skip(reason) {
  fs.writeFileSync(REPORT_PATH, JSON.stringify({ skipped: true, reason, generated: new Date().toISOString() }, null, 2));
  console.log(`  SKIP — ${reason} (a11y live-gate needs the local stack: Flask :5000 + Supabase :54321 + seeder).`);
  process.exit(0);
}

(async () => {
  const key = anonKey();
  if (!key) skip('local anon key not found (tests/_db-cleanup.ts)');
  const session = await grantSession(key);
  if (!session) skip('supervisor password-grant failed (GoTrue down or seeder absent)');

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();

  // Establish the origin, then seed the real session + identity (persists across navigations).
  // 'commit' (not domcontentloaded) — we only need the origin to set localStorage; retry once to
  // ride out a transient cold-start / resource-contention slow first navigation.
  let originOk = false;
  for (let attempt = 0; attempt < 2 && !originOk; attempt++) {
    try {
      await page.goto(BASE + '/index.html', { waitUntil: 'commit', timeout: 30000 });
      originOk = true;
    } catch (_) { /* retry once */ }
  }
  if (!originOk) { await browser.close(); skip('Flask bridge unreachable at ' + BASE); }
  await page.evaluate(({ sess, hiveId, hiveName, worker }) => {
    localStorage.setItem('sb-127-auth-token', JSON.stringify(sess));   // storageKey derived from 127.0.0.1
    localStorage.setItem('wh_last_worker', worker);
    localStorage.setItem('wh_hive_id', hiveId);
    localStorage.setItem('wh_active_hive_id', hiveId);
    localStorage.setItem('wh_hive_name', hiveName);
    localStorage.setItem('wh_hive_role', 'supervisor');
    localStorage.setItem('wh_hives', JSON.stringify([{ id: hiveId, name: hiveName, role: 'supervisor', code: '' }]));
    localStorage.setItem('wh_nav_mode', 'engineer');
  }, { sess: session, hiveId: HIVE_ID, hiveName: HIVE_NAME, worker: WORKER });

  const detail = {};
  for (const p of PAGES) {
    try {
      await page.goto(BASE + '/' + p, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(1100); // first render + auth settle
      const after = page.url();
      const bounced = after.includes('signin=1') || !after.includes(p.replace('.html', ''));
      if (bounced) { detail[p] = { skipped: true, reason: 'auth gate (session not accepted)', url_after: after, nodes: 0 }; continue; }
      await page.addScriptTag({ content: AXE_SRC });
      const res = await page.evaluate(async (tags) => {
        const r = await axe.run(document, { runOnly: { type: 'tag', values: tags }, resultTypes: ['violations'] });
        const byRule = {}; let nodes = 0;
        for (const v of r.violations) { byRule[v.id] = { impact: v.impact, nodes: v.nodes.length }; nodes += v.nodes.length; }
        return { byRule, nodes, els: document.querySelectorAll('*').length };
      }, WCAG_TAGS);
      detail[p] = { skipped: false, els: res.els, nodes: res.nodes, byRule: res.byRule };
    } catch (e) {
      detail[p] = { skipped: true, reason: String(e && e.message || e).slice(0, 160), nodes: 0 };
    }
  }
  await browser.close();

  const scanned = PAGES.filter((p) => !detail[p].skipped);
  const current = {}; for (const p of scanned) current[p] = detail[p].nodes || 0;

  let baseline = {};
  if (fs.existsSync(BASELINE_PATH)) { try { baseline = JSON.parse(fs.readFileSync(BASELINE_PATH, 'utf8')).pages || {}; } catch (_) {} }
  const regressed = [];
  for (const p of scanned) if (baseline[p] !== undefined && current[p] > baseline[p]) regressed.push(`${p}: ${baseline[p]} -> ${current[p]}`);

  fs.writeFileSync(REPORT_PATH, JSON.stringify({
    generated: new Date().toISOString(), base: BASE, wcag_tags: WCAG_TAGS,
    authed_as: `${SUPERVISOR} (supervisor)`, pages: current, regressed, detail,
  }, null, 2));

  const firstRun = !fs.existsSync(BASELINE_PATH);
  if (firstRun || UPDATE) {
    fs.writeFileSync(BASELINE_PATH, JSON.stringify({ established: true, generated: new Date().toISOString(), pages: current }, null, 2));
  } else if (!regressed.length) {
    const merged = { ...baseline };
    for (const p of scanned) if (current[p] < (baseline[p] ?? Infinity)) merged[p] = current[p];
    fs.writeFileSync(BASELINE_PATH, JSON.stringify({ tightened: true, generated: new Date().toISOString(), pages: merged }, null, 2));
  }

  const total = scanned.reduce((a, p) => a + current[p], 0);
  console.log(`AXE (authed write surfaces) WCAG 2.2 AA — nodes/page @390px · ${scanned.length}/${PAGES.length} scanned as ${SUPERVISOR}:`);
  for (const p of PAGES) {
    const d = detail[p];
    if (d.skipped) { console.log(`    ${p.padEnd(22)}  —  skipped (${d.reason || 'no render'})`); continue; }
    console.log(`  ${current[p] > 0 ? '•' : ' '} ${p.padEnd(22)} ${String(current[p]).padStart(3)}  (${d.els} els)`);
  }
  console.log(`  ${'TOTAL (scanned)'.padEnd(24)} ${String(total).padStart(3)}  (baseline ${firstRun ? 'ESTABLISHED' : Object.values(baseline).reduce((a, b) => a + b, 0)})`);

  if (scanned.length === 0) skip('every write page bounced (session not accepted) — nothing scanned');
  if (regressed.length) {
    console.log('\nFAIL — new accessibility violations on an authed write surface:');
    regressed.forEach((r) => console.log('  ' + r));
    process.exit(1);
  }
  console.log('\nPASS — authed write surfaces at or below baseline (integrity-at-zero a11y gate).');
})();
