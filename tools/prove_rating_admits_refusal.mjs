/* prove_rating_admits_refusal.mjs — T88: a rating that was refused must not look accepted.
 *
 * Every companion reply carries thumbs up/down. The tap used to lock BOTH buttons and paint the
 * chosen one green or red IMMEDIATELY, then fire the insert and discard whatever came back.
 *
 * ★AND THE MOST LIKELY FAILURE DOES NOT THROW. supabase-js returns { error } on an RLS refusal
 * rather than raising, so the try/catch around the insert never fired for it - the code's own
 * comment records that anon callers "silently skip". A worker tapped thumbs-down, watched it turn
 * red, and nothing was stored. That is worse than having no thumbs at all: it teaches them their
 * feedback is being read when it is not, on the surface whose entire purpose is to collect it.
 *
 * THE ASSERTION, against the shipped function: _recordReplyRating resolves FALSE when the write is
 * refused, and TRUE when it lands. That return value is what the UI now commits to - it colours the
 * button only on true, and hands both buttons back on false so the worker can retry.
 *
 * ★BOTH DIRECTIONS, because a function that always reported failure would satisfy the first half
 * while silently discarding every real rating.
 *
 * Probe rows are marked WH-T88-PROBE and deleted afterwards, with a re-count to prove it.
 *
 * Usage: node tools/prove_rating_admits_refusal.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234' };
const MARK = 'WH-T88-PROBE';

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();

const hive = psql(`SELECT hm.hive_id FROM hive_members hm JOIN auth.users u ON u.id=hm.auth_uid
                   WHERE u.email='${ACCT.email}' AND hm.status='active' LIMIT 1;`).split('\n')[0];
if (!hive) { console.log('SKIP — no active hive for the test account'); process.exit(0); }

const v = {};
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

  const drive = async (refuse) => {
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
    if (refuse) {
      // the shape a real RLS denial takes: a non-2xx with a body, NOT an exception
      await page.route('**/rest/v1/ai_reply_feedback*', (r) => r.fulfill({
        status: 403, contentType: 'application/json',
        body: JSON.stringify({ message: 'new row violates row-level security policy' }),
      }));
    }
    await page.goto(`${BASE}/logbook.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(
      () => !!(window.WHVoice && typeof window.WHVoice._recordReplyRating === 'function'),
      { timeout: 25000 }).catch(() => {});
    const out = await page.evaluate(async (mark) => {
      const V = window.WHVoice;
      if (!V || typeof V._recordReplyRating !== 'function') return { noApi: true };
      const r = await V._recordReplyRating(-1, mark + ' question', mark + ' answer');
      return { result: r };
    }, MARK);
    await page.close();
    return { ...out, errs: errs.length };
  };

  v.refused = await drive(true);
  v.stored = await drive(false);
  const rows = Number(psql(`SELECT count(*) FROM ai_reply_feedback WHERE question LIKE '${MARK}%';`)) || 0;
  v.rowsWritten = rows;
  console.log(`  insert refused (403) -> returned ${JSON.stringify(v.refused.result)}`);
  console.log(`  insert allowed       -> returned ${JSON.stringify(v.stored.result)} | rows in table: ${rows}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 170);
  console.log('probe error:', v.error);
} finally {
  try {
    psql(`DELETE FROM ai_reply_feedback WHERE question LIKE '${MARK}%';`);
    v.leftBehind = Number(psql(`SELECT count(*) FROM ai_reply_feedback WHERE question LIKE '${MARK}%';`)) || 0;
  } catch (_) { v.leftBehind = 'cleanup failed'; }
  await browser.close();
}

const pass = !v.error && v.refused && v.stored && !v.refused.noApi
  && v.refused.result === false      // a refusal is reported, not swallowed
  && v.stored.result === true        // and a real rating still succeeds
  && v.rowsWritten === 1
  && v.leftBehind === 0
  && v.refused.errs === 0 && v.stored.errs === 0;

if (!pass && !v.error) {
  console.log('  A refused rating that reports success paints the button as accepted and drops the');
  console.log('  worker\'s answer. supabase returns { error } on an RLS denial - it does not throw.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — rating admits refusal: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
