// perf_scale_sweep.mjs — Arc L · L0: the LIVE Speed-lens sweep (CWV + transfer weight).
//
// WHY (PERFORMANCE_SCALE_ROADMAP.md §1 + §4): the static miner
// (mine_perf_scale_surfaces.py) scores Efficiency/Budget/Resilience from source
// (page weight, query boundedness, SW coverage). The SPEED lens (S) — Core Web
// Vitals LCP/INP/CLS — can only be MEASURED in a real browser. This sweep drives
// each user-facing page, recovers buffered CWV via ufai_battery's observers, drives
// one interaction for INP, captures real transfer weight, scores the S cell, folds
// it into perf_scale_results.json, and ratchets perf_scale_baseline.json.
//
// REUSE (not reinvent) — identical recipe to frontend_ufai_sweep.mjs:
//   - :5000 seeder serves pages repointed to local 127.0.0.1:54321
//   - sign in ONCE on a lenient page (shift-brain); session persists same-origin
//   - install ufai_battery (window.__UFAI) → boot() → cwv() (buffered LCP/CLS;
//     INP after a driven click). The battery is the authoritative CWV referee.
//
// USAGE:
//   node tools/perf_scale_sweep.mjs                 # measure CWV all user-facing pages
//   node tools/perf_scale_sweep.mjs --page index.html
//   node tools/perf_scale_sweep.mjs --headed
//   node tools/perf_scale_sweep.mjs --accept        # write/ratchet baseline (forward-only)
//   node tools/perf_scale_sweep.mjs --accept --update-baseline
//
// Output: merges S-cell status into perf_scale_results.json + perf_scale_baseline.json

import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync } from 'fs';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const EMAIL = process.env.WH_TEST_EMAIL || 'leandromarquez@auth.workhiveph.com';
const PASSWORD = process.env.WH_TEST_PASSWORD || 'test1234';
const HIVE = '9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7'; // Baguio Textile Mills
const WORKER = process.env.WH_TEST_WORKER || 'Leandro Marquez';
const PAGE_QUERY = { 'marketplace-seller-profile.html': '?worker=Bryan%20Garcia' };

const args = process.argv.slice(2);
const HEADED = args.includes('--headed');
const ACCEPT = args.includes('--accept');
const UPDATE_BASELINE = args.includes('--update-baseline');
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
// median-of-N (roadmap §5: CWV is environment-sensitive → measure median-of-N). Default
// 1 for a quick run; baseline-lock uses --median 3 so the ratchet is stable.
const MEDIAN_N = (() => { const i = args.indexOf('--median'); return i >= 0 ? Math.max(1, parseInt(args[i + 1]) || 1) : 1; })();
// S ratchet tolerance — live CWV jitters ±1-2 even at median-of-N; S may dip this much
// without a real regression (E/R/B are static/deterministic → zero tolerance).
const S_TOLERANCE = 2;
const RESULTS = 'perf_scale_results.json';
const BASELINE = 'perf_scale_baseline.json';

// 2026 Google "good" CWV thresholds (same as ufai_battery CWV_GOOD).
const CWV_GOOD = { LCP: 2500, INP: 200, CLS: 0.1 };
// Transfer-weight budget per page (real bytes over the wire — gzipped is smaller
// than the raw doc; this is the network cost a worker on PH 4G actually pays).
const TRANSFER_BUDGET = 1024 * 1024; // 1 MB transferred

const BATTERY_SRC = readFileSync('ufai_battery.js', 'utf8');

async function signInOnce(context) {
  const page = await context.newPage();
  await page.goto(`${SEEDER}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.supabase, { timeout: 15000 }).catch(() => {});
  const r = await page.evaluate(async ({ email, password, hive, worker }) => {
    try {
      const db = window._whSupabaseClient || window.getDb('http://127.0.0.1:54321', window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email, password });
      localStorage.setItem('wh_active_hive_id', hive);
      localStorage.setItem('wh_last_worker', worker);
      return { ok: !error && !!data?.session, err: error ? String(error.message || error) : null };
    } catch (e) { return { ok: false, err: String(e) }; }
  }, { email: EMAIL, password: PASSWORD, hive: HIVE, worker: WORKER });
  await page.close();
  return r;
}

async function measurePage(context, pageFile) {
  const page = await context.newPage();
  try {
    await page.goto(`${SEEDER}/workhive/${pageFile}${PAGE_QUERY[pageFile] || ''}`, { waitUntil: 'load', timeout: 30000 });
    await page.waitForTimeout(2500); // settle async render (LCP often lands post-fetch)

    // ── install the battery + boot the CWV observers (buffered: recovers LCP/CLS
    //    even though we inject after load) ──
    let raw = { LCP: null, INP: null, CLS: null };
    try {
      await page.evaluate(`(${BATTERY_SRC})()`);
      await page.evaluate(`(async()=>{ try { await window.__UFAI.boot(); } catch(e){} })()`);
      await page.waitForTimeout(400);
      raw = await page.evaluate(() => window.__UFAI.cwv());
    } catch (e) { /* battery unavailable → CWV stays null (honest: pending) */ }
    // freeze passive LCP/CLS (page-load values) BEFORE any interaction — a driven
    // click ADDS layout shift a passive user never sees (verifier wxjtoqvu0).
    const cwv = { LCP: raw && raw.LCP != null ? raw.LCP : null, CLS: raw && raw.CLS != null ? raw.CLS : null, INP: null };

    // ── drive a REAL, TRUSTED interaction (page.mouse, not a script click) so a
    //    PerformanceEventTiming with interactionId fires → INP measures for real.
    //    A synthetic page.evaluate() el.click() is untrusted and NEVER yields INP. ──
    try {
      const box = await page.evaluate(() => {
        const vis = el => { const b = el.getBoundingClientRect(); const s = getComputedStyle(el); return b.width > 0 && b.height > 0 && b.top >= 0 && b.top < innerHeight && s.visibility !== 'hidden' && s.display !== 'none'; };
        const isShell = el => !!(el.closest && el.closest('[id^="wh-ai"],[id^="wh-hub"],#wh-companion,.wh-hub'));
        const el = [...document.querySelectorAll('button,a[href^="#"],[role="tab"],.view-tab,.tab-btn,summary')].find(e => vis(e) && !isShell(e));
        if (!el) return null;
        const b = el.getBoundingClientRect();
        return { x: Math.round(b.x + b.width / 2), y: Math.round(b.y + b.height / 2) };
      });
      if (box) await page.mouse.click(box.x, box.y);
      else await page.mouse.click(195, 390); // viewport-center fallback (still trusted)
      await page.waitForTimeout(700);
      const c2 = await page.evaluate(() => window.__UFAI.cwv());
      if (c2 && c2.INP != null) cwv.INP = c2.INP;  // INP ONLY — never re-adopt LCP/CLS
    } catch (e) { /* INP best-effort; null → honestly marked not-measured */ }

    // ── real transfer weight (what the network actually shipped) ──
    const weight = await page.evaluate(() => {
      const res = performance.getEntriesByType('resource');
      const nav = performance.getEntriesByType('navigation')[0];
      const sum = res.reduce((a, r) => a + (r.transferSize || 0), 0) + (nav ? (nav.transferSize || 0) : 0);
      return { transferBytes: sum, resourceCount: res.length };
    });

    await page.close();
    return { cwv, weight };
  } catch (e) {
    await page.close().catch(() => {});
    return { error: String(e).slice(0, 140) };
  }
}

function scoreS(cwv, weight) {
  // S pass = measured LCP within budget AND CLS within budget. INP is reported but
  // does NOT silently pass-credit when unmeasured (verifier wxjtoqvu0): if INP was
  // measured it gates; if not, the cell is stamped inp_measured:false and the `why`
  // says so — no implied 3rd-vital credit. Local serving is fast (roadmap §5) → a
  // LOCAL pass is necessary-not-sufficient for PH-4G prod; that caveat is persisted.
  const have = cwv && cwv.LCP != null;
  if (!have) {
    return { status: 'pending', inp_measured: false, why: 'CWV not captured (LCP null) - battery/observer did not register a paint' };
  }
  const lcpOk = cwv.LCP <= CWV_GOOD.LCP;
  const clsOk = cwv.CLS == null || cwv.CLS <= CWV_GOOD.CLS;
  const inpMeasured = cwv.INP != null;
  const inpOk = !inpMeasured || cwv.INP <= CWV_GOOD.INP;
  const wOk = !weight || weight.transferBytes <= TRANSFER_BUDGET;
  const pass = lcpOk && clsOk && inpOk;
  const transferKB = weight && weight.transferBytes > 0 ? Math.round(weight.transferBytes / 1024) : null;
  const inpStr = inpMeasured ? cwv.INP + 'ms' + (inpOk ? '' : 'X') : 'not-measured';
  return {
    status: pass ? 'pass' : 'fix',
    inp_measured: inpMeasured,
    measured: `LCP=${cwv.LCP}ms${lcpOk ? '' : 'X'} INP=${inpStr} CLS=${cwv.CLS == null ? 'n/a' : cwv.CLS + (clsOk ? '' : 'X')}` +
      (transferKB != null ? ` transfer=${transferKB}KB${wOk ? '' : 'X'}` : ' transfer=cache-hit'),
    why: `[LOCAL fast server - LCP optimistic vs PH-4G prod (roadmap s5); local pass necessary-not-sufficient] ` +
      `LCP<=2.5s CLS<=0.1${inpMeasured ? ' INP<=200ms' : ' (INP NOT measured - needs trusted interaction)'}; transfer-weight noted, not gating S`,
  };
}

// median of an array of numbers (nulls dropped)
function median(arr) {
  const a = arr.filter(x => x != null).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : Math.round((a[m - 1] + a[m]) / 2 * 1000) / 1000;
}

// measure a page MEDIAN_N times and take the median CWV per vital (roadmap §5)
async function measurePageMedian(context, pageFile) {
  const runs = [];
  for (let i = 0; i < MEDIAN_N; i++) {
    const r = await measurePage(context, pageFile);
    if (r.error) { if (i === 0) return r; continue; }
    runs.push(r);
  }
  if (!runs.length) return { error: 'all runs failed' };
  const cwv = {
    LCP: median(runs.map(r => r.cwv.LCP)),
    INP: median(runs.map(r => r.cwv.INP)),
    CLS: median(runs.map(r => r.cwv.CLS)),
  };
  // transfer: take the MAX (the cold-load value; later loads are cache-warmed to 0)
  const weight = { transferBytes: Math.max(...runs.map(r => (r.weight ? r.weight.transferBytes : 0))) };
  return { cwv, weight, runs: runs.length };
}

(async () => {
  if (!existsSync(RESULTS)) { console.error(`[L0] ${RESULTS} missing — run mine_perf_scale_surfaces.py first.`); process.exit(2); }
  const results = JSON.parse(readFileSync(RESULTS, 'utf8'));
  const pageSurfaces = Object.entries(results.surfaces)
    .filter(([sid, s]) => s.layer === 'L1' && s.lenses && s.lenses.S && s.lenses.S.applicable)
    .map(([sid, s]) => ({ sid, page: sid.replace('page::', ''), rec: s }))
    .filter(x => !PAGE_ONLY || x.page === PAGE_ONLY);

  const browser = await chromium.launch({ headless: !HEADED });
  const context = await browser.newContext({ viewport: { width: 390, height: 780 } }); // mobile-first field viewport
  const si = await signInOnce(context);
  console.log(`[L0] sign-in: ${si.ok ? 'OK' : 'FAIL ' + si.err}`);

  let nPass = 0, nFix = 0, nPending = 0;
  const findings = [];
  console.log(`[L0] measuring CWV median-of-${MEDIAN_N} per page...`);
  for (const { sid, page, rec } of pageSurfaces) {
    const res = await measurePageMedian(context, page);
    if (res.error) { console.log(`  ${page.padEnd(36)} ERROR ${res.error}`); rec.lenses.S.status = 'pending'; rec.lenses.S.measured = 'error: ' + res.error; rec.lenses.S.inp_measured = false; nPending++; continue; }
    const s = scoreS(res.cwv, res.weight);
    rec.lenses.S.status = s.status;
    rec.lenses.S.measured = s.measured;
    rec.lenses.S.why = s.why;                  // persist the env caveat (was dropped)
    rec.lenses.S.inp_measured = s.inp_measured;
    rec.lenses.S.env = 'local';
    rec.lenses.S.lcp_local_optimistic = true;
    rec.lenses.S.cwv = res.cwv;                // clean scalars only (no stale ratings)
    rec.lenses.S.transferKB = res.weight && res.weight.transferBytes > 0 ? Math.round(res.weight.transferBytes / 1024) : 'cache-hit';
    let mark = s.status === 'pass' ? '✓' : s.status === 'fix' ? '✗' : '·';
    if (s.status === 'pass') nPass++;
    else if (s.status === 'fix') { nFix++; findings.push({ page, why: s.measured }); }
    else nPending++;
    console.log(`  ${page.padEnd(36)} S:${mark}  ${s.measured}`);
  }
  await browser.close();

  // ── recompute the S-lens aggregate INTO the results (mirror the miner's math) ──
  let sPass = 0, sDenom = 0, sPending = 0;
  for (const s of Object.values(results.surfaces)) {
    const c = s.lenses && s.lenses.S;
    if (!c || !c.applicable) continue;
    sDenom++;
    if (c.status === 'pass') sPass++;
    else if (c.status === 'pending') sPending++;
  }
  results.lens_pass.S = sPass;
  results.lens_pending.S = sPending;
  results.lens_pct.S = sDenom ? Math.round(1000 * sPass / sDenom) / 10 : 0;
  results.S_sweep = { ran: new Date().toISOString(), pages_measured: pageSurfaces.length, pass: nPass, fix: nFix, pending: nPending, findings };

  console.log('\n' + '='.repeat(64));
  console.log('ARC L — L0 SPEED (CWV) sweep');
  console.log('='.repeat(64));
  console.log(`  pages measured : ${pageSurfaces.length}`);
  console.log(`  S PASS         : ${nPass}`);
  console.log(`  S FIX          : ${nFix}`);
  console.log(`  S pending      : ${nPending}`);
  console.log(`  S lens overall : ${sPass}/${sDenom} = ${results.lens_pct.S}% (incl. ${sPending} non-page pending: edge/calc p95)`);
  if (findings.length) { console.log('\n  S FIX findings:'); for (const f of findings) console.log(`    ${f.page}: ${f.why}`); }

  // ── forward-only ratchet across all 4 lenses ──
  if (ACCEPT) {
    const cur = { S_pass: results.lens_pass.S, E_pass: results.lens_pass.E, R_pass: results.lens_pass.R, B_pass: results.lens_pass.B };
    if (UPDATE_BASELINE || !existsSync(BASELINE)) {
      writeFileSync(BASELINE, JSON.stringify({ ...cur, set: new Date().toISOString() }, null, 2));
      console.log(`\n[L] baseline ${UPDATE_BASELINE ? 'UPDATED' : 'created'}: S>=${cur.S_pass}, E>=${cur.E_pass}, R>=${cur.R_pass}, B>=${cur.B_pass}`);
    } else {
      const base = JSON.parse(readFileSync(BASELINE, 'utf8'));
      let failed = false;
      // E/R/B are static/deterministic → zero tolerance. S is live CWV → allow a
      // S_TOLERANCE dip (median-of-N jitter), real regressions still exceed it.
      const tol = { S_pass: S_TOLERANCE, E_pass: 0, R_pass: 0, B_pass: 0 };
      for (const k of ['S_pass', 'E_pass', 'R_pass', 'B_pass']) {
        if (base[k] != null && cur[k] < base[k] - tol[k]) { console.error(`[L] RATCHET FAIL: ${k} ${cur[k]} < baseline ${base[k]}${tol[k] ? ` (tol ${tol[k]})` : ''}`); failed = true; }
      }
      if (failed) { writeFileSync(RESULTS, JSON.stringify(results, null, 2)); process.exit(1); }
      console.log(`\n[L] ratchet OK: S ${cur.S_pass}>=${base.S_pass}-${S_TOLERANCE}, E ${cur.E_pass}>=${base.E_pass}, R ${cur.R_pass}>=${base.R_pass}, B ${cur.B_pass}>=${base.B_pass}`);
    }
  }

  writeFileSync(RESULTS, JSON.stringify(results, null, 2));
  console.log(`\n  -> merged S status into ${RESULTS}`);
})();
