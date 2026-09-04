/* prove_stock_ripple.mjs — T11's cross-page write-propagation ripple oracle (2026-08-26).
 *
 * THE ORACLE: a stock write on page A must be VISIBLE on page B within one reload.
 * cross_surface_agreement locks READ-parity (two pages reading one datum agree); nothing locked
 * WRITE-propagation — the worker who issues the last spare must see the low-stock consequence
 * appear on the ops-home tile, or the supervisor plans tomorrow on yesterday's number.
 *
 * The walk: stage a part at min_qty+1 (one deduct away from low-stock), read index's low-stock
 * tile (pre), issue 1 through inventory's OWN Use modal (openUseModal -> #use-submit-btn -> the
 * atomic inventory_deduct RPC), then reload index: the tile must read pre+1.
 *
 * Staging + hygiene: the part's original qty is snapshotted and RESTORED; the probe's
 * inventory_transactions rows (job_ref WH-T11-PROBE) are deleted; both verified. The staging
 * UPDATE is itself a probe mutation — scoped to one row, reverted in cleanup.
 *
 * Usage: node tools/prove_stock_ripple.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const ACCT = { email: 'bryangarcia@auth.workhiveph.com', pw: 'test1234', worker: 'Bryan Garcia' };
const JOB_REF = 'WH-T11-PROBE ripple';

function psql(sql) {
  return execFileSync('docker',
    ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
    { encoding: 'utf8' }).trim();
}

async function signInDirect(page) {
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  // getDb EXISTS from utils.js load but THROWS until the supabase lib arrives — wait for createClient.
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  return page.evaluate(async ({ email, password, worker, hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    const { error } = await db.auth.signInWithPassword({ email, password });
    if (error) return { ok: false, err: error.message };
    try {
      localStorage.setItem('wh_worker_name', worker);
      localStorage.setItem('wh_last_worker', worker);
      localStorage.setItem('wh_active_hive_id', hive.id);
      localStorage.setItem('wh_hive_id', hive.id);
      localStorage.setItem('wh_hive_name', hive.name);
      localStorage.setItem('wh_hive_role', 'worker');
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
    return { ok: true };
  }, { email: ACCT.email, password: ACCT.pw, worker: ACCT.worker, hive: HIVE });
}

async function readLowStockTile(page) {
  await page.goto(`${SEEDER}/index.html`, { waitUntil: 'domcontentloaded' });
  // ★MEASURE THE SETTLED STATE, NOT THE FIRST PAINT (2026-08-31). The original returned the FIRST
  // number the tile rendered. index paints the tile from a fast fallback path and only then settles
  // it from the get_hive_dashboard RPC — so on the post-deduct read this probe could grab the
  // pre-ripple value while the fresh RPC was still in flight, reporting "NO ripple" about a page
  // that was about to show one (the 2026-08-31 full board's stock-ripple FAIL fit exactly this:
  // deducted=true, cleanup=true, tile 3->3). Diagnosed against the live DB: membership, view
  // definition and RPC source were all sound, which left the instrument. Now: never return before
  // MIN_DWELL (the RPC's settle time), and only return a value that has held STABLE for STABLE_MS —
  // a genuinely stale tile still returns its stale number and fails the gate honestly.
  const MIN_DWELL = 4000, STABLE_MS = 2000, CAP = 30000;
  const t0 = Date.now();
  let last = null, lastAt = 0;
  while (Date.now() - t0 < CAP) {
    const n = await page.evaluate(() => {
      const tile = document.querySelector('[data-kpi="low-stock"]');
      if (!tile) return null;
      const m = (tile.innerText || '').match(/\d+/);
      return m ? Number(m[0]) : null;
    });
    if (n !== null) {
      if (n !== last) { last = n; lastAt = Date.now(); }
      else if (Date.now() - t0 >= MIN_DWELL && Date.now() - lastAt >= STABLE_MS) return n;
    }
    await page.waitForTimeout(500);
  }
  if (last !== null) return last;   // capped out while a value existed: report the last seen
  throw new Error('low-stock tile never rendered a number');
}

// ── stage: one deduct away from low-stock. ★STAGE VIA min_qty, NOT qty_on_hand (2026-09-01).
// qty_on_hand is LEDGER-DERIVED: trg_inventory_sync_balance (inventory_sync_balance_from_ledger)
// recomputes it from the inventory_transactions ledger on every write, so a direct
// `UPDATE ... SET qty_on_hand` is silently reverted by the deduct's OWN trigger. Measured today:
// staged qty 61, one UI deduct, qty read 204 (= ledgerSum 205 - 1), never 60 - so the part was
// never actually low, the tile honestly stayed 3, and this gate red-flagged a bug that did not
// exist (an oracle bug, not a product bug: a straight psql set-to-min + one reload paints 4 fine).
// min_qty is a PLAIN CONFIG column the ledger trigger never touches, so raising it to
// qty_on_hand-1 leaves the part not-low now (qty > min) and exactly one real deduct from
// qty == min_qty -> is_low_stock. Threshold staged where it survives the write path.
const row = psql(`SELECT id, qty_on_hand, min_qty FROM inventory_items
  WHERE hive_id='${HIVE.id}' AND status='approved' AND qty_on_hand >= 2
  ORDER BY qty_on_hand DESC LIMIT 1`);
if (!row) { console.log('ABORT: no stageable part (approved, qty >= 2) in the fixture hive.'); process.exit(2); }
const [PART_ID, ORIG_QTY, ORIG_MIN] = row.split('|');
const STAGE_MIN = Number(ORIG_QTY) - 1;   // qty > min now (not low); one deduct -> qty == min -> low
psql(`UPDATE inventory_items SET min_qty = ${STAGE_MIN} WHERE id='${PART_ID}'`);
console.log(`staged: part ${PART_ID} qty ${ORIG_QTY}, min ${ORIG_MIN} -> ${STAGE_MIN} (one deduct crosses qty<=min)`);

const browser = await chromium.launch();
let verdict = { pre: null, post: null, deducted: false, rippled: false, cleanup_ok: false };
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  const s = await signInDirect(page);
  if (!s.ok) throw new Error('sign-in failed: ' + s.err);

  verdict.pre = await readLowStockTile(page);
  console.log('index low-stock tile (pre):', verdict.pre);

  // ── issue 1 through the page's own Use modal ──
  await page.goto(`${SEEDER}/inventory.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof window.openUseModal === 'function', { timeout: 25000 });
  // loadInventory() must know the part before openUseModal can find it
  const tW = Date.now();
  while (Date.now() - tW < 20000) {
    const known = await page.evaluate((id) => {
      try { return !!(typeof loadInventory === 'function' && loadInventory().find(i => i.id === id)); }
      catch (_) { return false; }
    }, PART_ID);
    if (known) break;
    await page.waitForTimeout(700);
  }
  await page.evaluate((id) => openUseModal(id), PART_ID);
  await page.waitForSelector('#use-modal', { state: 'visible', timeout: 10000 });
  await page.fill('#use-qty', '1');
  await page.fill('#use-job-ref', JOB_REF);
  await page.click('#use-submit-btn');
  const tD = Date.now();
  while (Date.now() - tD < 20000) {
    const n = psql(`SELECT count(*) FROM inventory_transactions WHERE item_id='${PART_ID}' AND job_ref LIKE '%WH-T11-PROBE%'`);
    if (n === '1') { verdict.deducted = true; break; }
    await page.waitForTimeout(700);
  }
  if (!verdict.deducted) throw new Error('the Use submit left no transaction row within 20s');
  console.log('deduct landed:', psql(`SELECT qty_on_hand FROM inventory_items WHERE id='${PART_ID}'`), `on hand (= min ${STAGE_MIN}, now low-stock)`);

  // ── the ripple: index's tile reads pre+1 after one reload ──
  verdict.post = await readLowStockTile(page);
  verdict.rippled = verdict.post === verdict.pre + 1;
  console.log('index low-stock tile (post):', verdict.post, verdict.rippled ? '(+1, rippled)' : '(NO ripple)');
  // ★INSTRUMENTATION (2026-08-31): the server chain was proven sound in psql (staged deduct ->
  // view flips -> get_hive_dashboard AS the probe's user returns the +1 count), yet the settled
  // tile still read the pre value. So on a miss, ask the RPC directly IN THIS browser context and
  // print what IT says — splitting "the RPC fails in-page (silent empty-catch at index.html:4412,
  // page renders a fallback)" from "the RPC returns +1 in-page and the RENDER drops it".
  if (!verdict.rippled) {
    const probe = await page.evaluate(async () => {
      try {
        const db = (typeof getDb === 'function') ? getDb() : window.db;
        const dayStart = new Date(new Date().setHours(0, 0, 0, 0)).toISOString();
        const r = await db.rpc('get_hive_dashboard', {
          p_hive_id: localStorage.getItem('wh_active_hive_id'), p_day_start: dayStart });
        return { err: r.error ? String(r.error.message || r.error.code) : null,
                 count: r.data ? r.data.low_stock_count : null };
      } catch (e) { return { err: 'threw: ' + (e && e.message) }; }
    });
    console.log('rpc_direct_in_page:', JSON.stringify(probe));
  }
} finally {
  // No time window: probe-marked rows are artifacts BY DEFINITION, and a window narrower than
  // the verify once left an earlier session's orphan (-4, WO-9001) failing this run's cleanup.
  // Order matters: DELETE the probe's -1 tx FIRST so the ledger CHAIN HEAD reverts to ORIG_QTY
  // (the chain trigger tg_inventory_txn_chain_qty_after fires on INSERT only, so the delete does
  // NOT itself re-sync qty_on_hand), THEN restore qty_on_hand=ORIG_QTY explicitly to realign the
  // stored balance with that reverted chain head (leaving them equal = no reconcile drift), and
  // restore min_qty (plain config).
  psql(`DELETE FROM inventory_transactions WHERE job_ref LIKE '%WH-T11-PROBE%' OR note LIKE '%WH-T11-PROBE%'`);
  psql(`UPDATE inventory_items SET qty_on_hand = ${ORIG_QTY}, min_qty = ${ORIG_MIN} WHERE id='${PART_ID}'`);
  const q = psql(`SELECT qty_on_hand FROM inventory_items WHERE id='${PART_ID}'`);
  const m = psql(`SELECT min_qty FROM inventory_items WHERE id='${PART_ID}'`);
  const tx = psql(`SELECT count(*) FROM inventory_transactions WHERE job_ref LIKE '%WH-T11-PROBE%'`);
  verdict.cleanup_ok = q === ORIG_QTY && m === ORIG_MIN && tx === '0';
  await browser.close();
}
console.log('cleanup verified:', verdict.cleanup_ok);
const pass = verdict.deducted && verdict.rippled && verdict.cleanup_ok;
console.log((pass ? 'PASS' : 'FAIL') + ` — stock ripple: tile ${verdict.pre} -> ${verdict.post} after the Use (deducted=${verdict.deducted}, cleanup=${verdict.cleanup_ok})`);
process.exit(pass ? 0 : 1);
