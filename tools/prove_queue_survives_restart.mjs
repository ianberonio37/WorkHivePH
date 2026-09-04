/* prove_queue_survives_restart.mjs — T14: the queue survives closing the app (2026-08-27).
 *
 * prove_offline_queued.mjs proves the write is HELD offline; prove_queue_drain.mjs proves it DRAINS
 * exactly once on reconnect. Both do it inside ONE page life. The field reality they skip is the
 * one that actually happens: a worker in a dead zone logs the work, pockets the phone, and the PWA
 * is gone by the time signal returns - killed by the OS, or just closed. Between the enqueue and
 * the reconnect there is a RESTART.
 *
 * That is not a variation on the drain test, it is a different failure surface, and T14 already
 * paid to learn why. The queue is created by a `_ensure<X>Queue()` accessor and its auto-sync is
 * attached inside that accessor - so the drain only ever happens if a FRESH page life calls it. The
 * measured defer race on pm-scheduler (2 of 5 runs silently never created the queue) was exactly
 * this wiring failing on ONE page load. A queue whose rows persist but whose sync is never
 * re-attached after a restart is strictly worse than no queue: the work is neither sent nor lost,
 * it is invisible, and the worker was told it was saved.
 *
 * THE ORACLE, in five assertions:
 *   1. HELD     - offline, the enqueue lands and nothing reaches the server.
 *   2. PERSISTS - after a full document restart, the item is STILL in IndexedDB. Read from the
 *                 store directly, not through the page's queue object, because the page's object is
 *                 exactly what a restart destroys - asking it would be asking the wrong witness.
 *   3. REWIRED  - the fresh page life re-creates its queue and re-attaches auto-sync. This is the
 *                 defer-race question asked of the restart path.
 *   4. DRAINED  - back online, the row reaches the table.
 *   5. ONCE     - exactly one row after a further settle, and the store is empty. A restart must not
 *                 turn one queued write into two.
 *
 * Subject: dayplanner's schedule_items queue, the same one prove_queue_drain uses - a plain row,
 * no FK cascade, no ledger side-effects, so a marked probe row costs nothing and cleans up whole.
 * Writes a MARKED row and deletes it; ABORTS rather than measure on dirty state.
 *
 * Usage: node tools/prove_queue_survives_restart.mjs [--teeth]
 *   --teeth reproduces the defer-race outcome on the restarted document, so the REWIRED
 *   assertion can be shown to go red against the defect it was built for.
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const ACCT = { email: 'bryangarcia@auth.workhiveph.com', worker: 'Bryan Garcia' };
const TEETH = process.argv.includes('--teeth');
const MARKER = 'WH-T14-RESTART-PROBE';
const QUEUE_DB = 'wh_dayplanner_offline';
const QUEUE_STORE = 'pending';

function psql(sql) {
  return execFileSync('docker',
    ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
    { encoding: 'utf8' }).trim();
}

const countRows = () =>
  psql(`SELECT count(*) FROM schedule_items WHERE title LIKE '%${MARKER}%' OR notes LIKE '%${MARKER}%'`);

const cleanup = () => {
  psql(`DELETE FROM schedule_items WHERE title LIKE '%${MARKER}%' OR notes LIKE '%${MARKER}%'`);
  return countRows() === '0';
};

const pre = countRows();
if (pre !== '0') {
  console.log(`ABORT: ${pre} leftover probe row(s) - refusing to measure on dirty state.`);
  process.exit(2);
}

// Read the queue's IndexedDB store WITHOUT going through the page's queue object.
const readStore = (page) => page.evaluate(({ db, store }) => new Promise((resolve) => {
  let req;
  try { req = indexedDB.open(db); } catch (e) { return resolve({ error: 'open threw' }); }
  req.onerror = () => resolve({ error: 'open failed' });
  req.onsuccess = () => {
    const idb = req.result;
    if (!idb.objectStoreNames.contains(store)) return resolve({ n: 0, note: 'store absent' });
    try {
      const all = idb.transaction(store, 'readonly').objectStore(store).getAll();
      all.onsuccess = () => resolve({ n: (all.result || []).length });
      all.onerror = () => resolve({ error: 'getAll failed' });
    } catch (e) { resolve({ error: 'tx threw' }); }
  };
}), { db: QUEUE_DB, store: QUEUE_STORE });

const goOffline = async (ctx, page) => {
  await page.evaluate(() => Object.defineProperty(navigator, 'onLine', { get: () => false, configurable: true }));
  await ctx.setOffline(true);
};

const browser = await chromium.launch();
const verdict = {
  held: false, serverWritesWhileOffline: null, persistedAcrossRestart: false,
  rewiredAfterRestart: false, drained: false, once: false, queueEmptied: false, cleanup: false,
};
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  // addInitScript survives navigation, which is the whole point here - the restart must come back
  // up still believing it is offline, the way a phone in a dead zone does.
  await page.addInitScript(() => Object.defineProperty(navigator, 'onLine', { get: () => false, configurable: true }));

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

  // ── 1. HELD ────────────────────────────────────────────────────────────────────────────────
  let serverWrites = 0;
  await ctx.route('**/rest/v1/schedule_items**', (route) => { serverWrites++; return route.abort(); });
  await goOffline(ctx, page);

  const enq = await page.evaluate(async (marker) => {
    if (!window.whCreateQueue) return 'no queue helper on this page';
    const q = (typeof _ensureDpQueue === 'function' ? _ensureDpQueue() : null) || window._whDpQueue;
    if (!q || typeof q.enqueue !== 'function') return 'page queue not reachable';
    // Same row shape dayplanner enqueues: schedule_items RLS is auth_uid = auth.uid() on write, so
    // a row without the signed-in identity is correctly refused at drain time and would read as
    // "the queue does not drain" - a false red against a working product.
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    const { data: { session } } = await db.auth.getSession();
    const rowId = 'sch-' + Date.now();
    await q.enqueue({ id: rowId, op: 'upsert', payload: {
      id: rowId, title: marker + ' task', notes: marker,
      date: new Date().toISOString().slice(0, 10),
      auth_uid: session && session.user ? session.user.id : null,
      worker_name: localStorage.getItem('wh_worker_name'),
    } });
    const pend = await q.getPending();
    return 'enqueued:' + ((pend || []).length);
  }, MARKER);
  console.log('offline enqueue ->', enq);
  verdict.held = String(enq).startsWith('enqueued:') && !String(enq).endsWith(':0');
  verdict.serverWritesWhileOffline = serverWrites;

  // ── 2. PERSISTS across a real restart ──────────────────────────────────────────────────────
  // A fresh document. Everything the page held in memory - the queue object, its auto-sync
  // listener, the whole JS heap - is gone, exactly as it is when the OS reclaims a backgrounded PWA.
  //
  // THE DOCUMENT IS FETCHED WITH THE TRANSPORT UP, DELIBERATELY. With serviceWorkers blocked there
  // is no cached shell, so a goto under setOffline(true) dies at ERR_INTERNET_DISCONNECTED - a
  // failure of the SHELL, which is not what this prover claims. Whether the SW serves the app cold
  // and offline is a real question and a separate one (T44's territory); folding it in here would
  // make this go red for a reason unrelated to the queue, the same way a check written against
  // "visible" rather than "tagged" fails for reasons unrelated to its subject.
  //
  // The restart window stays write-tight regardless: the schedule_items route is still aborted, and
  // addInitScript means the fresh document comes up with navigator.onLine === false, so the page
  // believes it is offline and never attempts a drain. Nothing can reach the table here, which the
  // ONCE assertion below re-checks from the database anyway.
  // --teeth reproduces the defect this assertion exists for, on the RESTARTED page only. The
  // measured defer race did not throw or warn: whCreateQueue simply was not there when the one-shot
  // check ran, so the queue was never created and every later capture fell through to the dead
  // network. Making the property permanently undefined on the fresh document reaches the same end
  // state, so a green run here would mean the prover cannot see the thing it was built to see.
  if (TEETH) {
    console.log('--- TEETH: suppressing whCreateQueue on the restarted document ---');
    await page.addInitScript(() => {
      try {
        Object.defineProperty(window, 'whCreateQueue',
          { get: () => undefined, set: () => {}, configurable: false });
      } catch (_) { /* empty-catch-allow: if it cannot be pinned the run simply is not a teeth run */ }
    });
  }
  await ctx.setOffline(false);
  await page.goto(`${SEEDER}/dayplanner.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  await goOffline(ctx, page);
  const midRestart = countRows();
  if (midRestart !== '0') {
    console.log(`   NOTE: ${midRestart} row(s) reached the table during the restart window - the`
              + ` write-tight assumption did not hold, so ONCE below is measuring something else.`);
  }

  const stored = await readStore(page);
  console.log('after restart, IndexedDB store ->', JSON.stringify(stored));
  verdict.persistedAcrossRestart = !stored.error && stored.n >= 1;

  // ── 3. REWIRED: did the fresh page life re-create its queue and re-attach auto-sync? ────────
  const wiring = await page.evaluate(async () => {
    const created = !!window._whDpQueue
      || !!(typeof _ensureDpQueue === 'function' && _ensureDpQueue());
    const q = window._whDpQueue;
    let pending = null;
    try { pending = q ? (await q.getPending() || []).length : null; } catch (_) { pending = null; }
    return { created, pending, hasAutoSync: !!(q && typeof q.startAutoSync === 'function') };
  });
  console.log('after restart, wiring ->', JSON.stringify(wiring));
  verdict.rewiredAfterRestart = !!wiring.created && wiring.pending >= 1;

  // ── 4+5. DRAINED, ONCE ─────────────────────────────────────────────────────────────────────
  await ctx.unroute('**/rest/v1/schedule_items**');
  await ctx.setOffline(false);
  await page.evaluate(() => {
    Object.defineProperty(navigator, 'onLine', { get: () => true, configurable: true });
    window.dispatchEvent(new Event('online'));
  });
  const t0 = Date.now();
  while (Date.now() - t0 < 30000) {
    if (countRows() !== '0') { verdict.drained = true; break; }
    await page.waitForTimeout(1500);
  }
  const rows = countRows();
  await page.waitForTimeout(6000);          // let a second tick try to double-write
  const rowsAfter = countRows();
  verdict.once = rows === '1' && rowsAfter === '1';
  const left = await readStore(page);
  verdict.queueEmptied = !left.error && left.n === 0;
  console.log(`drained: rows=${rows} after-settle=${rowsAfter} storeLeft=${JSON.stringify(left)}`);
} catch (e) {
  console.log('probe error:', String(e).slice(0, 220));
} finally {
  verdict.cleanup = cleanup();
  await browser.close();
}

const pass = verdict.held && verdict.serverWritesWhileOffline === 0 && verdict.persistedAcrossRestart
          && verdict.rewiredAfterRestart && verdict.drained && verdict.once && verdict.queueEmptied
          && verdict.cleanup;
console.log((pass ? 'PASS' : 'FAIL') + ` — queue survives restart: ${JSON.stringify(verdict)}`);
process.exit(pass ? 0 : 1);
