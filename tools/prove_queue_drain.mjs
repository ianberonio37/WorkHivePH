/* prove_queue_drain.mjs — T14's other half: the queue DRAINS on reconnect, exactly once (2026-08-26).
 *
 * prove_offline_queued.mjs proves the first half — offline, the write is HELD and the person is
 * told. Its header says plainly why the second half was left out: "drains exactly once on
 * reconnect ... needs a reconnect plus a settle window, which makes a different, slower test; doing
 * it badly is worse than not doing it, because a drain probe that reconnects into a shared database
 * writes real rows." So this test exists on those terms - it writes a MARKED row, and it deletes it.
 *
 * THE ORACLE, in three assertions:
 *   1. HELD    - offline, the enqueue lands in the queue's own store and nothing reaches the server.
 *   2. DRAINED - back online, the row appears in the target table (the promise the banner made).
 *   3. ONCE    - exactly one row, and the queue's store is empty afterwards. A drain that fires twice
 *                is the silent corruption this whole family exists to prevent.
 *
 * Subject: dayplanner's schedule_items queue (whCreateQueue-backed: a plain row with no FK cascade
 * and no ledger side-effects, so a probe row costs nothing and cleans up completely).
 *
 * Usage: node tools/prove_queue_drain.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const ACCT = { email: 'bryangarcia@auth.workhiveph.com', worker: 'Bryan Garcia' };
const MARKER = 'WH-T14-DRAIN-PROBE';

function psql(sql) {
  return execFileSync('docker',
    ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
    { encoding: 'utf8' }).trim();
}

const cleanup = () => {
  psql(`DELETE FROM schedule_items WHERE title LIKE '%${MARKER}%' OR notes LIKE '%${MARKER}%'`);
  return psql(`SELECT count(*) FROM schedule_items WHERE title LIKE '%${MARKER}%' OR notes LIKE '%${MARKER}%'`) === '0';
};

const pre = psql(`SELECT count(*) FROM schedule_items WHERE title LIKE '%${MARKER}%' OR notes LIKE '%${MARKER}%'`);
if (pre !== '0') { console.log(`ABORT: ${pre} leftover probe row(s) - refusing to measure on dirty state.`); process.exit(2); }

const browser = await chromium.launch();
const verdict = { held: false, serverWritesWhileOffline: null, drained: false, once: false, queueEmptied: false, cleanup: false };
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();

  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  await page.evaluate(async ({ email, worker, hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email, password: 'test1234' });
    try {
      localStorage.setItem('wh_worker_name', worker);
      localStorage.setItem('wh_last_worker', worker);
      localStorage.setItem('wh_active_hive_id', hive.id);
      localStorage.setItem('wh_hive_id', hive.id);
      localStorage.setItem('wh_hive_name', hive.name);
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
  }, { email: ACCT.email, worker: ACCT.worker, hive: HIVE });

  await page.goto(`${SEEDER}/dayplanner.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(4000);

  // ── go offline the way the queue actually sees it: navigator.onLine AND the network ──
  await page.addInitScript(() => Object.defineProperty(navigator, 'onLine', { get: () => false, configurable: true }));
  await page.evaluate(() => Object.defineProperty(navigator, 'onLine', { get: () => false, configurable: true }));
  let serverWrites = 0;
  await ctx.route('**/rest/v1/schedule_items**', (route) => { serverWrites++; return route.abort(); });
  await ctx.setOffline(true);

  // enqueue through the queue helper the page owns
  const enq = await page.evaluate(async (marker) => {
    if (!window.whCreateQueue) return 'no queue helper on this page';
    const q = (typeof _ensureDpQueue === 'function' ? _ensureDpQueue() : null) || window._whDpQueue;
    if (!q || typeof q.enqueue !== 'function') return 'page queue not reachable';
    // schedule_items RLS is `auth_uid = auth.uid()` on write, so a probe row WITHOUT auth_uid is
    // correctly refused at drain time - the first run of this prover read that refusal as "the queue
    // does not drain", which would have been a false red against a working product. Enqueue the row
    // the way the page does: with the signed-in identity on it.
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    const { data: { session } } = await db.auth.getSession();
    // The queue item shape is { id, op, payload } - the drain reads item.payload. A flat row
    // enqueued fine and then drained nothing, which the second run of this prover almost recorded
    // as "the queue does not drain". Enqueue exactly as dayplanner does at :769.
    const rowId = 'sch-' + Date.now();
    const payload = {
      id: rowId, title: marker + ' task', notes: marker,
      date: new Date().toISOString().slice(0, 10),
      auth_uid: session && session.user ? session.user.id : null,
      worker_name: localStorage.getItem('wh_worker_name'),
    };
    await q.enqueue({ id: rowId, op: 'upsert', payload });
    const pend = await q.getPending();
    return 'enqueued:' + ((pend || []).length);
  }, MARKER);
  console.log('offline enqueue ->', enq);
  verdict.held = String(enq).startsWith('enqueued:') && !String(enq).endsWith(':0');
  verdict.serverWritesWhileOffline = serverWrites;

  // ── reconnect, let auto-sync fire ──
  await ctx.unroute('**/rest/v1/schedule_items**');
  await ctx.setOffline(false);
  await page.evaluate(() => {
    Object.defineProperty(navigator, 'onLine', { get: () => true, configurable: true });
    window.dispatchEvent(new Event('online'));
  });
  const t0 = Date.now();
  while (Date.now() - t0 < 30000) {
    const n = psql(`SELECT count(*) FROM schedule_items WHERE title LIKE '%${MARKER}%'`);
    if (n !== '0') { verdict.drained = true; verdict.once = n === '1'; break; }
    await page.waitForTimeout(1500);
  }
  const rows = psql(`SELECT count(*) FROM schedule_items WHERE title LIKE '%${MARKER}%'`);
  // give a second drain tick a chance to double-write before declaring "once"
  await page.waitForTimeout(6000);
  const rowsAfter = psql(`SELECT count(*) FROM schedule_items WHERE title LIKE '%${MARKER}%'`);
  verdict.once = rows === '1' && rowsAfter === '1';
  verdict.queueEmptied = await page.evaluate(async () => {
    const q = window._whDpQueue;
    try { if (!q) return false; const pend = await q.getPending(); return (pend || []).length === 0; }
    catch (_) { return false; }
  });
  console.log(`drained: rows=${rows} after-settle=${rowsAfter} queueEmptied=${verdict.queueEmptied}`);
} catch (e) {
  console.log('probe error:', String(e).slice(0, 200));
} finally {
  verdict.cleanup = cleanup();
  await browser.close();
}

const pass = verdict.held && verdict.serverWritesWhileOffline === 0 && verdict.drained && verdict.once
          && verdict.queueEmptied && verdict.cleanup;
console.log((pass ? 'PASS' : 'FAIL') + ` — queue drain: ${JSON.stringify(verdict)}`);
process.exit(pass ? 0 : 1);
