/* prove_filter_vocabulary_is_complete.mjs — T64: a filter must offer everyone who acted.
 *
 * audit-log's feed reads the newest 500 rows, which is right for a scrolling feed. The filter
 * dropdowns were then built from THAT array, so the choices offered were whatever happened to
 * appear inside the cap.
 *
 * ★MEASURED on the fixture hive: 3,402 audit rows, 4 distinct actors and 22 distinct actions
 * overall - but only 3 actors and 18 actions inside the newest 500. A supervisor could not filter
 * to one of the four people who acted, or to 4 of the 22 action types, and nothing said the list
 * was partial. On a compliance surface "no option for that person" reads as "that person did
 * nothing", which is the opposite of what an audit trail is for. Same class this file already
 * fixed for the CSV export, one function away.
 *
 * THE ASSERTION: the option lists match the DISTINCT values in the database, not the capped page.
 * The database is the oracle - the counts are computed there and compared to what the page offers,
 * so this cannot drift into checking the page against itself.
 *
 * ★AND IT WOULD HAVE MISSED A REAL BUG WITHOUT A LIVE LOAD. The first version of the fix declared
 * its cache with `let` further down the file than the async path that reads it - a temporal dead
 * zone - so the page threw ReferenceError on first paint and every dropdown came back EMPTY. No
 * syntax check sees that; only opening the page does.
 *
 * Usage: node tools/prove_filter_vocabulary_is_complete.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234' };

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();

const hive = psql(`SELECT hm.hive_id FROM hive_members hm JOIN auth.users u ON u.id=hm.auth_uid
                   WHERE u.email='${ACCT.email}' AND hm.status='active' LIMIT 1;`).split('\n')[0];
if (!hive) { console.log('SKIP — no active hive for the test account'); process.exit(0); }

const truth = {
  rows:    Number(psql(`SELECT count(*) FROM hive_audit_log WHERE hive_id='${hive}';`)) || 0,
  actors:  Number(psql(`SELECT count(DISTINCT actor) FROM hive_audit_log WHERE hive_id='${hive}' AND actor IS NOT NULL;`)) || 0,
  actions: Number(psql(`SELECT count(DISTINCT action) FROM hive_audit_log WHERE hive_id='${hive}' AND action IS NOT NULL;`)) || 0,
};
if (truth.rows <= 500) {
  console.log(`SKIP — only ${truth.rows} audit rows, below the 500 cap, so the cap cannot hide anything`);
  process.exit(0);
}

const v = { truth };
const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  const auth = await ctx.newPage();
  await auth.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await auth.waitForFunction(
    () => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
    { timeout: 20000 }).catch(() => {});
  const ok = await auth.evaluate(async ({ acct, url, hiveId }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
      localStorage.setItem('wh_active_hive_id', hiveId);
      localStorage.setItem('wh_hive_id', hiveId);
      localStorage.setItem('wh_last_worker', 'Leandro Marquez');
      localStorage.setItem('wh_hive_role', 'supervisor');
      return !error && !!data?.session;
    } catch (_) { return false; }
  }, { acct: ACCT, url: SB_URL, hiveId: hive });
  await auth.close();
  if (!ok) throw new Error('sign-in failed');

  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 110)));
  await page.goto(`${BASE}/audit-log.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(14000);
  v.page = await page.evaluate(() => ({
    actors: document.querySelectorAll('#actor-filter-options option').length,
    actions: document.querySelectorAll('#action-filter-options option').length,
  }));
  v.page.errs = errs.length;
  v.firstError = errs[0] || null;
  console.log(`  database: ${truth.actors} actors, ${truth.actions} actions across ${truth.rows} rows`);
  console.log(`  offered : ${v.page.actors} actors, ${v.page.actions} actions`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 170);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const p = v.page || {};
const pass = !v.error && p.errs === 0
  && p.actors === truth.actors && p.actions === truth.actions;

if (!pass && !v.error) {
  console.log('  A filter that omits someone who acted tells the reader they did nothing. The feed may');
  console.log('  be capped; the vocabulary of who and what may not be.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — filter vocabulary is complete: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
