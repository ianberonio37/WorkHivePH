/* prove_photo_survives_queue.mjs — T14: an attached photo survives the queue and a restart (2026-08-27).
 *
 * The dead-zone entry a worker most wants to keep is the one with the picture on it: the cracked
 * bearing, the leak, the burnt contactor. logbook writes that photo into the row's `photo` column,
 * and offline the whole row goes into IndexedDB - so the question is whether the PICTURE comes back
 * intact after the phone has been pocketed and the app has been closed.
 *
 * SCOPE, STATED HONESTLY. This does NOT drive the full save form; prove_offline_queued.mjs's
 * logbook-entry case already proves form -> queue, including that the save is a form SUBMIT rather
 * than a click on a zero-width button. What was never proven is photo FIDELITY through storage and
 * a restart, and that is what this measures. The photo half is driven for real: a genuine PNG is
 * handed to the page's own #f-photo input, and the page's own pipeline (FileReader -> Image ->
 * canvas -> toDataURL, plus its 700KB re-encode guard) produces the data URL. Only the row's other
 * required fields are supplied directly, because the asset picker and tasklist gate are already
 * covered and re-driving them here would test someone else's assertion.
 *
 * THE ORACLE:
 *   1. PRODUCED  - the page turns a real image file into a compressed JPEG data URL.
 *   2. QUEUED    - offline, the row carrying that data URL lands in wh_logbook_offline, and NOTHING
 *                  reaches the server.
 *   3. SURVIVES  - after a full document restart the stored photo is byte-identical. Compared in
 *                  full, not by length: a truncated or re-encoded string has the same shape as an
 *                  intact one, and "roughly the right size" is how a corrupted image passes a test.
 *   4. STILL AN IMAGE - the survivor decodes back to a bitmap with real dimensions. A string can
 *                  round-trip perfectly and still be a broken picture.
 *
 * Writes NOTHING to the database - the row never leaves the queue, so there is nothing to clean up
 * server-side and no PM mirror, XP ledger or embedding is disturbed. The queue entry is removed at
 * the end and the removal is verified.
 *
 * Usage: node tools/prove_photo_survives_queue.mjs [--teeth]
 *   --teeth stores a photo of exactly the SAME LENGTH with one character changed. SURVIVES must go
 *   false while both lengths still match - which is the only way to show the comparison is byte-wise
 *   and not the "roughly the right size" check that lets a corrupted image pass.
 */
import { chromium } from 'playwright';
import zlib from 'node:zlib';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const ACCT = { email: 'bryangarcia@auth.workhiveph.com', worker: 'Bryan Garcia' };
const QUEUE_DB = 'wh_logbook_offline';
const QUEUE_STORE = 'pending';
const TEETH = process.argv.includes('--teeth');
const PROBE_ID = 'WH-T14-PHOTO-PROBE-' + Date.now();

/* A real PNG, big enough that the page's compressor has something to do - a 1x1 stub would make
 * every assertion below true for the wrong reason. Written by hand because the repo has no image
 * dependency and adding one for a fixture would be a poor trade. */
function makePng(w, h) {
  const crcTable = (() => {
    const t = new Int32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c;
    }
    return t;
  })();
  const crc32 = (buf) => {
    let c = 0xffffffff;
    for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, 'ascii'), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td));
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; ihdr[9] = 2; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;   // 8-bit RGB
  const raw = Buffer.alloc(h * (1 + w * 3));
  let o = 0;
  for (let y = 0; y < h; y++) {
    raw[o++] = 0;                                   // filter: none
    for (let x = 0; x < w; x++) {                   // structure, so JPEG cannot flatten it away
      raw[o++] = (x * 7 + y * 3) & 0xff;
      raw[o++] = (x ^ y) & 0xff;
      raw[o++] = (x * 3 + y * 11) & 0xff;
    }
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0)),
  ]);
}

const readStore = (page) => page.evaluate(({ db, store }) => new Promise((resolve) => {
  let req;
  try { req = indexedDB.open(db); } catch (e) { return resolve({ error: 'open threw' }); }
  req.onerror = () => resolve({ error: 'open failed' });
  req.onsuccess = () => {
    const idb = req.result;
    if (!idb.objectStoreNames.contains(store)) return resolve({ rows: [], note: 'store absent' });
    try {
      const all = idb.transaction(store, 'readonly').objectStore(store).getAll();
      all.onsuccess = () => resolve({ rows: (all.result || []).map((r) => ({ id: r.id, photo: r.photo })) });
      all.onerror = () => resolve({ error: 'getAll failed' });
    } catch (e) { resolve({ error: 'tx threw' }); }
  };
}), { db: QUEUE_DB, store: QUEUE_STORE });

const browser = await chromium.launch();
const verdict = { produced: false, queued: false, serverWrites: null, survives: false,
                  stillAnImage: false, cleaned: false };
let producedLen = 0, survivorLen = 0;
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
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

  await page.goto(`${SEEDER}/logbook.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);

  // ── 1. PRODUCED: the page's own photo pipeline turns a real file into a data URL ────────────
  await page.setInputFiles('#f-photo', {
    name: 'defect.png', mimeType: 'image/png', buffer: makePng(420, 320),
  });
  await page.waitForFunction(() => typeof currentPhotoData === 'string' && currentPhotoData.length > 100,
    { timeout: 15000 }).catch(() => {});
  const produced = await page.evaluate(() => (typeof currentPhotoData === 'string' ? currentPhotoData : ''));
  producedLen = produced.length;
  verdict.produced = produced.startsWith('data:image/jpeg;base64,') && produced.length > 1000;
  console.log(`produced data URL: ${producedLen} chars, prefix ok = ${produced.startsWith('data:image/jpeg;base64,')}`);

  // ── 2. QUEUED offline, with zero server traffic ────────────────────────────────────────────
  let serverWrites = 0;
  await ctx.route('**/rest/v1/logbook**', (route) => { serverWrites++; return route.abort(); });
  await page.evaluate(() => Object.defineProperty(navigator, 'onLine', { get: () => false, configurable: true }));
  await ctx.setOffline(true);

  const enq = await page.evaluate(async ({ id, teeth }) => {
    if (typeof queueEntryOffline !== 'function') return 'no queueEntryOffline on this page';
    // The row the page itself builds at save time, carrying the photo IT produced.
    await queueEntryOffline({
      id, date: new Date().toISOString().slice(0, 10),
      machine: 'PHOTO PROBE', category: 'Inspection', problem: id, action: id,
      photo: teeth ? (function (s) {
        // same length, one character different - a corruption a length check cannot see
        const i = s.length - 8, c = s[i] === 'A' ? 'B' : 'A';
        return s.slice(0, i) + c + s.slice(i + 1);
      })(currentPhotoData) : currentPhotoData,
      status: 'Open',
      worker_name: localStorage.getItem('wh_worker_name'),
    });
    const pend = await getPendingEntries();
    return 'queued:' + (pend || []).length;
  }, { id: PROBE_ID, teeth: TEETH });
  console.log('offline enqueue ->', enq);
  verdict.queued = String(enq).startsWith('queued:') && !String(enq).endsWith(':0');
  verdict.serverWrites = serverWrites;

  // ── 3. SURVIVES a full document restart ────────────────────────────────────────────────────
  await ctx.setOffline(false);                     // transport for the SHELL only; see the restart prover
  await page.goto(`${SEEDER}/logbook.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await ctx.setOffline(true);

  const after = await readStore(page);
  const row = (after.rows || []).find((r) => r.id === PROBE_ID);
  survivorLen = row && row.photo ? row.photo.length : 0;
  verdict.survives = !!row && row.photo === produced;
  console.log(`after restart: row found = ${!!row}, photo ${survivorLen} chars, identical = ${verdict.survives}`);

  // ── 4. STILL AN IMAGE: the survivor decodes to a real bitmap ────────────────────────────────
  if (row && row.photo) {
    const dims = await page.evaluate((src) => new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight });
      img.onerror = () => resolve({ w: 0, h: 0 });
      img.src = src;
    }), row.photo);
    verdict.stillAnImage = dims.w > 0 && dims.h > 0;
    console.log(`survivor decodes to ${dims.w}x${dims.h}`);
  }

  // ── cleanup: the row never left the queue, so this is the whole of it ───────────────────────
  await page.evaluate(async (id) => {
    try { await removeFromQueue(id); } catch (_) { /* empty-catch-allow: verified below */ }
  }, PROBE_ID);
  const left = await readStore(page);
  verdict.cleaned = !(left.rows || []).some((r) => r.id === PROBE_ID);
} catch (e) {
  console.log('probe error:', String(e).slice(0, 220));
} finally {
  await browser.close();
}

const pass = verdict.produced && verdict.queued && verdict.serverWrites === 0
          && verdict.survives && verdict.stillAnImage && verdict.cleaned;
console.log((pass ? 'PASS' : 'FAIL')
  + ` — photo survives queue: ${JSON.stringify({ ...verdict, producedLen, survivorLen })}`);
process.exit(pass ? 0 : 1);
