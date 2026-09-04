/* prove_hive_rename_reaches.mjs — T140: a rename must reach the OTHER devices (2026-08-26).
 *
 * ★THIS EXISTS BECAUSE THE TRAJECTORY'S RECORDED PREMISE WAS WRONG, IN BOTH HALVES. T140's basis
 * read that hive rename "does not exist - no UI, no update path (grep: zero rename/hive_name edit
 * sites in hive.html)", and concluded that no stale-name propagation class could exist. But
 * hive.html renames a hive, and a live test showed the consequence: after another device renamed
 * the plant, this session kept showing the OLD name on its board and in its chrome, because every
 * page trusts localStorage.wh_hive_name and nothing re-read hives.name. That cache is written at
 * join/switch time, so "eventually" can mean weeks. A grep that misses one line can turn a real
 * defect into a recorded absence.
 *
 * THE SHAPE OF THE TEST is the only one that can see it: the rename happens OUTSIDE the session
 * being measured (straight into the database, exactly as another supervisor's browser would), and
 * then this session loads the board. A test that renamed through this same page would prove only
 * that a page can update itself, which was never in doubt.
 *
 * THREE ASSERTIONS:
 *   cacheCorrected   localStorage.wh_hive_name now holds the new name
 *   glassCorrected   the board title shows it
 *   staleGone        the old name appears NOWHERE on the page - the assertion that matters, because
 *                    a chrome that updates its title while a sidebar keeps the old name is still
 *                    showing two truths
 *
 * The hive's name is restored in a finally block, and the restore is verified.
 *
 * Usage: node tools/prove_hive_rename_reaches.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d' };
const PROBE_NAME = 'WH-T140-PROBE Renamed Plant';

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();

const original = psql(`SELECT name FROM hives WHERE id = '${HIVE.id}'`).split('\n')[0];
if (!original) { console.log('SKIP — fixture hive not found.'); process.exit(0); }
console.log(`  hive: "${original}"`);

const browser = await chromium.launch();
const v = {};
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 120)));

  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  await page.evaluate(async ({ hive, name }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email: 'bryangarcia@auth.workhiveph.com', password: 'test1234' });
    try {
      localStorage.setItem('wh_worker_name', 'Bryan Garcia');
      localStorage.setItem('wh_last_worker', 'Bryan Garcia');
      localStorage.setItem('wh_active_hive_id', hive);
      localStorage.setItem('wh_hive_id', hive);
      localStorage.setItem('wh_hive_name', name);   // this device's cached, soon-to-be-stale name
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
  }, { hive: HIVE.id, name: original });

  // ANOTHER DEVICE renames the hive. This session knows nothing about it.
  psql(`UPDATE hives SET name = '${PROBE_NAME}' WHERE id = '${HIVE.id}'`);

  await page.goto(`${SEEDER}/hive.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(9000);

  const r = await page.evaluate((oldName) => ({
    cached: localStorage.getItem('wh_hive_name'),
    title: (document.getElementById('board-hive-name') || {}).textContent || '',
    stalePresent: document.body.innerText.includes(oldName),
  }), original);

  v.cacheCorrected = r.cached === PROBE_NAME;
  v.glassCorrected = r.title.trim() === PROBE_NAME;
  v.staleGone = r.stalePresent === false;
  v.pageerrors = errs.length;
  for (const [k, val] of Object.entries(v)) console.log(`  ${k.padEnd(18)} ${val}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 180);
  console.log('probe error:', v.error);
} finally {
  psql(`UPDATE hives SET name = '${original.replace(/'/g, "''")}' WHERE id = '${HIVE.id}'`);
  v.restored = psql(`SELECT name FROM hives WHERE id = '${HIVE.id}'`).split('\n')[0] === original;
  console.log(`  restored           ${v.restored}`);
  await browser.close();
}

const pass = !v.error && v.cacheCorrected && v.glassCorrected && v.staleGone
          && v.pageerrors === 0 && v.restored;
console.log((pass ? 'PASS' : 'FAIL') + ` — hive rename reaches: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
