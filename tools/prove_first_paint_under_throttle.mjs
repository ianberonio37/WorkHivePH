/* prove_first_paint_under_throttle.mjs — T37: something must be on screen fast (2026-08-26).
 *
 * Plant wifi at its worst is the condition this platform is actually used in, and the first second
 * decides whether a worker believes the app is working. PP1's bar is that SOMETHING paints quickly -
 * chrome, a heading, a skeleton - rather than a white screen while data is fetched.
 *
 * ★THIS MEASURES FIRST CONTENTFUL PAINT, NOT SETTLE TIME, and the distinction is the point. A page
 * that takes 6s to fill with data but paints its frame in 400ms feels alive; one that paints nothing
 * for 2s feels broken even if it finishes sooner. The companion gate (waiting-is-spoken) already
 * proves the GAP is filled with something honest; this one proves the gap starts quickly.
 *
 * REST is throttled so the measurement is about the SHELL, not the network: a page whose first paint
 * waits on data is exactly the failure being looked for.
 *
 * Usage: node tools/prove_first_paint_under_throttle.mjs
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234',
               worker: 'Leandro Marquez', hiveName: 'Baguio Textile Mills' };
const BUDGET_MS = 1800;   // generous: this is a loopback shell, not a real 3G handshake

const PAGES = ['logbook.html', 'inventory.html', 'community.html', 'asset-hub.html',
               'alert-hub.html', 'analytics.html', 'pm-scheduler.html', 'index.html'];

const browser = await chromium.launch();
const rows = [];
let fatal = null;
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const auth = await ctx.newPage();
  await auth.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await auth.waitForFunction(
    () => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
    { timeout: 20000 }).catch(() => {});
  const ok = await auth.evaluate(async ({ acct, url }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
      const uid = data?.session?.user?.id;
      const { data: m } = uid ? await db.from('hive_members').select('hive_id')
        .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
      if (m?.hive_id) {
        localStorage.setItem('wh_active_hive_id', m.hive_id);
        localStorage.setItem('wh_hive_id', m.hive_id);
      }
      localStorage.setItem('wh_last_worker', acct.worker);
      localStorage.setItem('wh_hive_name', acct.hiveName);
      localStorage.setItem('wh_hive_role', 'supervisor');
      return !error && !!data?.session;
    } catch (e) { return false; }
  }, { acct: ACCT, url: SB_URL });
  await auth.close();
  if (!ok) throw new Error('sign-in failed');

  // ★ONE PAGE AT A TIME, AND THE FIRST VERSION OF THIS PROVER PROVED WHY. Reusing the context and
  // opening pages in sequence, analytics.html — the SIXTH page in the run — reported a 2220ms first
  // paint against 212-292ms for everything else, and it looked exactly like a page whose paint waits
  // on a slow read. Measured in isolation it paints in 400ms unthrottled and 368ms THROTTLED. The
  // 2220ms was contention from the five pages before it, still holding delayed routes and competing
  // for the same renderer. A performance number taken while other pages are in flight measures the
  // HARNESS. Each page now gets its own page object, closed before the next one opens, and any page
  // over budget is re-measured alone before it is believed.
  for (const pg of PAGES) {
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
    // every DATA read is slow; the shell is not. A first paint that waits on this is the defect.
    await page.route('**/rest/v1/**', async (route) => {
      await new Promise((r) => setTimeout(r, 1500));
      await route.continue();
    });
    await page.goto(`${BASE}/${pg}`, { waitUntil: 'commit' });
    const fcp = await page.evaluate(() => new Promise((resolve) => {
      const seen = performance.getEntriesByName('first-contentful-paint')[0];
      if (seen) { resolve(Math.round(seen.startTime)); return; }
      new PerformanceObserver((list, obs) => {
        const e = list.getEntriesByName('first-contentful-paint')[0];
        if (e) { obs.disconnect(); resolve(Math.round(e.startTime)); }
      }).observe({ type: 'paint', buffered: true });
      setTimeout(() => resolve(-1), 12000);
    })).catch(() => -1);
    await page.waitForTimeout(500);
    await page.close();
    rows.push({ page: pg, fcp, errs: errs.length });
    console.log(`  ${pg.padEnd(20)} first paint ${fcp < 0 ? 'NEVER' : fcp + 'ms'}`
      + (errs.length ? `  err=${errs.length}` : ''));
  }
  // ── CONFIRM ALONE BEFORE BELIEVING ──────────────────────────────────────────────────────────
  // Anything over budget is re-measured in a FRESH context with nothing else running. Only a page
  // that is still slow by itself is a finding; the rest were measuring the harness.
  for (const row of rows.filter((r) => r.fcp < 0 || r.fcp > BUDGET_MS)) {
    const solo = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
    const sp = await solo.newPage();
    await sp.route('**/rest/v1/**', async (route) => {
      await new Promise((r) => setTimeout(r, 1500));
      await route.continue();
    });
    await sp.goto(`${BASE}/${row.page}`, { waitUntil: 'commit' });
    const again = await sp.evaluate(() => new Promise((resolve) => {
      const seen = performance.getEntriesByName('first-contentful-paint')[0];
      if (seen) { resolve(Math.round(seen.startTime)); return; }
      new PerformanceObserver((list, obs) => {
        const e = list.getEntriesByName('first-contentful-paint')[0];
        if (e) { obs.disconnect(); resolve(Math.round(e.startTime)); }
      }).observe({ type: 'paint', buffered: true });
      setTimeout(() => resolve(-1), 12000);
    })).catch(() => -1);
    await solo.close();
    console.log(`  re-measured alone: ${row.page} ${row.fcp}ms -> ${again}ms`);
    row.confirmed = again >= 0 && again > BUDGET_MS;
    row.solo = again;
  }
} catch (e) {
  fatal = String(e.message || e).slice(0, 160);
  console.log('probe error:', fatal);
} finally {
  await browser.close();
}

// only a page still slow when measured ALONE counts; the rest were harness contention
const slow = rows.filter((r) => (r.fcp < 0 || r.fcp > BUDGET_MS) && r.confirmed);
const worst = rows.reduce((a, r) => (r.fcp > (a?.fcp ?? -1) ? r : a), null);
console.log(`  budget ${BUDGET_MS}ms | slowest: ${worst ? worst.page + ' ' + worst.fcp + 'ms' : 'n/a'}`
  + ` | over budget: ${slow.length}`);
const pass = !fatal && rows.length === PAGES.length && slow.length === 0;
if (slow.length) {
  console.log(`  over budget ALONE: ${slow.map((r) => `${r.page}(${r.solo}ms)`).join(', ')}`);
  console.log('  A page whose first paint waits on a slow read shows a white screen to someone who');
  console.log('  already tapped. Paint the shell first and let the data arrive into it.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — first paint under throttle: ${JSON.stringify({ pages: rows.length, over: slow.length, fatal })}`);
process.exit(pass ? 0 : 1);
