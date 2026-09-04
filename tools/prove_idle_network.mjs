/* prove_idle_network.mjs — T118: what a page costs while NOBODY IS TOUCHING IT (2026-08-26).
 *
 * A worker at 8% battery at the end of a shift, and a tablet left running on a workshop wall, are
 * the same measurement: what does this page do when left alone? index was measured once (zero
 * requests in a full idle minute). The rest of the roster never was, and a polling loop is exactly
 * the kind of cost nobody notices while developing on mains power.
 *
 * THE MEASUREMENT: sign in, load the page, let it settle, then watch for 75 seconds with NO
 * interaction of any kind and count the HTTP requests it makes on its own. Requests are grouped by
 * URL so a red names the loop rather than just its size.
 *
 * ★WHAT THIS DOES NOT SEE, stated because a silent blind spot would make a zero misleading:
 * WEBSOCKETS. Supabase realtime holds a socket open and its frames are not HTTP requests, so a
 * realtime-heavy page can read zero here and still be doing work. That is not a flaw to fix by
 * inflating the number - a socket that is already open is genuinely cheaper than repeated polling -
 * but a zero on this gate means "no polling", never "no activity".
 *
 * ★AND SETTLING IS SEPARATE FROM IDLING. The first 8 seconds after load are the page fetching what
 * it exists to show; counting those would measure the boot, not the idle. The window opens after.
 *
 * Forward-only per page against tools/idle_network_baseline.json.
 *
 * Usage: node tools/prove_idle_network.mjs
 */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const BASELINE = 'tools/idle_network_baseline.json';
const SETTLE_MS = 8000;
// ★THE WINDOW MUST OUTLAST THE SLOWEST POLL, or a zero means nothing. The first run of this probe
// watched for 45s and reported ZERO idle requests on all eight pages - including alert-hub, which
// calls setInterval(loadAll, 60000) at line 559. A 60-second poll inside a 45-second window simply
// never fires, so the cleanest-looking result in the sweep was the page that polls hardest. The
// window is now 75s: longer than every interval found in the served roster (60000 is the largest),
// so each poll fires at least once inside it.
const WATCH_MS = 75000;

// the pages a phone sits on mid-shift, plus the wall-display candidates (T126)
const PAGES = ['index.html', 'logbook.html', 'pm-scheduler.html', 'alert-hub.html',
               'inventory.html', 'hive.html', 'dayplanner.html', 'analytics.html'];

const browser = await chromium.launch();
const results = [];
let pauseWorks = null;
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();

  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  await page.evaluate(async ({ hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email: 'bryangarcia@auth.workhiveph.com', password: 'test1234' });
    try {
      localStorage.setItem('wh_worker_name', 'Bryan Garcia');
      localStorage.setItem('wh_last_worker', 'Bryan Garcia');
      localStorage.setItem('wh_active_hive_id', hive.id);
      localStorage.setItem('wh_hive_id', hive.id);
      localStorage.setItem('wh_hive_name', hive.name);
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
  }, { hive: HIVE });

  for (const pg of PAGES) {
    await page.goto(`${SEEDER}/${pg}`, { waitUntil: 'domcontentloaded' });
    const where = await page.evaluate(() => location.pathname);
    if (!where.endsWith(pg)) { console.log(`  ${pg.padEnd(20)} SKIPPED — landed on ${where} (auth did not hold)`); continue; }
    // ★WAIT FOR THE NETWORK TO GO QUIET, NOT FOR A FIXED 8 SECONDS (2026-08-28). A constant settle
    // measures the MACHINE as much as the page: on a loaded host a slow boot spills past it and its
    // data reads get counted as "idle" traffic. That is not hypothetical - index.html has ZERO
    // setInterval and ZERO realtime channels, so it cannot poll by construction, and two runs of
    // this prover on that unchanged page reported 0 requests and then 12, the busiest endpoint
    // being v_logbook_truth: a boot read, arriving late. A gate whose verdict tracks how busy the
    // computer is will be disbelieved the first time someone re-runs it. networkidle is the real
    // signal that booting has finished; the timeout is a floor for pages that never fully settle
    // (a live subscription keeps a socket busy), and the fixed wait stays as the fallback.
    try {
      await page.waitForLoadState('networkidle', { timeout: 30000 });
    } catch (_) {
      await page.waitForTimeout(SETTLE_MS);        // never settled - fall back to the fixed floor
    }
    await page.waitForTimeout(1500);               // a beat after quiet, so a trailing read lands

    const seen = [];
    const onReq = (r) => seen.push(r.url());
    page.on('request', onReq);
    await page.waitForTimeout(WATCH_MS);            // no clicks, no keys, no scrolling
    page.off('request', onReq);

    const byUrl = {};
    for (const u of seen) {
      const key = u.replace(/[?&](apikey|access_token)=[^&]*/g, '').split('?')[0].slice(-70);
      byUrl[key] = (byUrl[key] || 0) + 1;
    }
    const top = Object.entries(byUrl).sort((a, b) => b[1] - a[1])[0];
    const perMin = Math.round((seen.length / (WATCH_MS / 1000)) * 60 * 10) / 10;
    results.push({ page: pg, requests: seen.length, perMin, top: top ? `${top[0]} x${top[1]}` : null });
    console.log(`  ${pg.padEnd(20)} ${String(seen.length).padStart(3)} requests in ${WATCH_MS / 1000}s `
      + `(~${perMin}/min)${top ? '  busiest: ' + top[0] + ' x' + top[1] : ''}`);
  }
  // ── THE PAUSE, which is what makes a 60s foreground poll acceptable ──────────────────────────
  // alert-hub refreshes every 60s while visible - correct for an alert board, and the busiest page
  // in this sweep at 11 requests per 75s. What makes that defensible rather than a battery leak is
  // that it STOPS when nobody is looking: it already wires visibilitychange to stopRefresh. Proven
  // rather than trusted, because a poll that keeps running in a backgrounded tab is invisible in
  // every foreground measurement, including the one above.
  await page.goto(`${SEEDER}/alert-hub.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(SETTLE_MS);
  const hidden = [];
  const onHiddenReq = (r) => hidden.push(r.url());
  page.on('request', onHiddenReq);
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { get: () => 'hidden', configurable: true });
    Object.defineProperty(document, 'hidden', { get: () => true, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await page.waitForTimeout(WATCH_MS);
  page.off('request', onHiddenReq);
  pauseWorks = hidden.length === 0;
  console.log(`
  alert-hub HIDDEN for ${WATCH_MS / 1000}s: ${hidden.length} requests `
    + `${pauseWorks ? '(poll paused — correct)' : '(STILL POLLING while nobody is looking)'}`);
} finally {
  await browser.close();
}

if (!results.length) { console.log('FAIL idle-network — NOTHING WAS MEASURED (no page graded).'); process.exit(1); }

const total = results.reduce((s, r) => s + r.requests, 0);
console.log(`\n  ${results.length} pages, ${total} idle requests total over ${WATCH_MS / 1000}s each`);

const now = Object.fromEntries(results.map((r) => [r.page, r.requests]));
if (!existsSync(BASELINE)) {
  writeFileSync(BASELINE, JSON.stringify({ perPage: now, watchSeconds: WATCH_MS / 1000, established: '2026-08-26' }, null, 1));
  console.log(`BASELINE established: ${JSON.stringify(now)} — forward-only`);
  process.exit(0);
}
const base = JSON.parse(readFileSync(BASELINE, 'utf8'));
// a small tolerance: a token refresh or a realtime re-handshake can land inside one window
if (pauseWorks === false) {
  console.log('FAIL idle-network — alert-hub kept polling while the tab was HIDDEN. A 60s refresh is '
    + 'right for an alert board somebody is watching; in a backgrounded tab it is a battery leak '
    + 'nobody can see.');
  process.exit(1);
}
const grew = results.filter((r) => r.requests > (base.perPage?.[r.page] ?? 0) + 2);
if (grew.length) {
  console.log('FAIL idle-network — a page got busier while nobody was touching it:');
  for (const g of grew) console.log(`    ${g.page}: ${base.perPage[g.page]} -> ${g.requests} requests (busiest: ${g.top})`);
  process.exit(1);
}
const improved = results.filter((r) => r.requests < (base.perPage?.[r.page] ?? 0) - 2);
if (improved.length) {
  base.perPage = now; base.ratcheted = 'auto';
  writeFileSync(BASELINE, JSON.stringify(base, null, 1));
  console.log(`PASS idle-network — quieter on ${improved.length} page(s); ratchet lowered.`);
  process.exit(0);
}
console.log('PASS idle-network — no page got busier at rest.');
process.exit(0);
