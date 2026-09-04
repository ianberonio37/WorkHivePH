/* prove_auto_read_retry.mjs — T126: a failed READ recovers itself on reconnect (2026-08-26).
 *
 * THE FINDING. This platform's reconnect handling was write-only: offline queues drain on 'online',
 * logbook syncs, banners repaint — but a failed READ just sat there behind a Retry button waiting
 * for a tap. "Manual" assumes somebody is standing there. A wall-mounted alert board has nobody, so
 * one network blip left a plant staring at a stale error for the rest of the shift; a phone in a
 * pocket has nobody at the exact moment the signal returns.
 *
 * FIVE ASSERTIONS, and three of them are restraint — an auto-retry that misbehaves is worse than
 * none, because it hammers a backend that is already unwell:
 *   1. registered   — whListError with a retry callback registers for auto-recovery.
 *   2. RECONNECT    — an 'online' event re-runs it. (The defect.)
 *   3. RATE FLOOR   — a second reconnect inside 3s does NOT re-run it.
 *   4. RECOVERED    — once the section is no longer showing an error, reconnect leaves it alone;
 *                     a person who already fixed it by hand must not have their view yanked.
 *   5. DETACHED     — an element removed from the document is dropped rather than retried forever,
 *                     so a re-rendering page cannot accumulate stale callbacks.
 *
 * ★NO TIMER, EVER. The retry fires on connectivity events only — 'online', and a tab becoming
 * visible after an offline spell. A polling retry would turn a backend outage into a self-inflicted
 * load test, which is the opposite of helping.
 *
 * Non-writing: stages an error panel in a detached probe element, fires events, reads counters.
 *
 * Usage: node tools/prove_auto_read_retry.mjs
 */
import { chromium } from 'playwright';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };

const browser = await chromium.launch();
let v = {};
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

  await page.goto(`${SEEDER}/logbook.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  const where = await page.evaluate(() => location.pathname);
  if (!/logbook\.html$/.test(where)) throw new Error(`not on logbook (${where}) — sign-in did not hold`);

  v = await page.evaluate(async () => {
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    const out = {};
    if (typeof whListError !== 'function') return { error: 'whListError missing' };
    out.helperPresent = typeof window.whRegisterAutoRetry === 'function';

    const host = document.createElement('div');
    host.id = 'wh-t126-probe';
    document.body.appendChild(host);
    let calls = 0;
    whListError(host, 'Probe: could not load.', function () { calls++; });

    out.noSpuriousCall = calls === 0;

    window.dispatchEvent(new Event('offline'));
    window.dispatchEvent(new Event('online'));
    await sleep(200);
    out.retriedOnReconnect = calls === 1;

    window.dispatchEvent(new Event('online'));           // inside the 3s floor
    await sleep(200);
    out.rateFloorHeld = calls === 1;

    host.innerHTML = '<p>recovered</p>';                 // no longer an error panel
    await sleep(3200);                                    // past the floor, so only state can stop it
    window.dispatchEvent(new Event('online'));
    await sleep(200);
    out.leftRecoveredAlone = calls === 1;

    // DETACHED: a fresh element, registered, then removed — it must not be retried
    const gone = document.createElement('div');
    document.body.appendChild(gone);
    let goneCalls = 0;
    whListError(gone, 'Probe: detached.', function () { goneCalls++; });
    gone.remove();
    await sleep(3200);
    window.dispatchEvent(new Event('online'));
    await sleep(200);
    out.droppedDetached = goneCalls === 0;

    host.remove();
    return out;
  });

  for (const [k, val] of Object.entries(v)) console.log(`  ${k.padEnd(22)} ${val}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 200);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const pass = !v.error && v.helperPresent && v.noSpuriousCall && v.retriedOnReconnect
          && v.rateFloorHeld && v.leftRecoveredAlone && v.droppedDetached;
console.log((pass ? 'PASS' : 'FAIL') + ` — auto read retry: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
