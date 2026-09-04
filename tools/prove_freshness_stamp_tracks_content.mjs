/* prove_freshness_stamp_tracks_content.mjs — T39: a freshness stamp must describe what is under it.
 *
 * alert-hub's AMC card serves the stored 6am brief instantly and then calls analytics-orchestrator
 * as a background UPGRADE. renderAmcCard stamps the meta line "stored brief, generated <time>",
 * which is exactly right while the stored copy is what is showing.
 *
 * ★THE UPGRADE REPLACED THE SUMMARY AND LEFT THE STAMP. On success the pane held a freshly composed
 * action brief under a line saying it came from this morning's stored row - the label had stopped
 * describing its content. Not a stale number, a stale CLAIM ABOUT a number, which is harder to
 * catch because everything on screen looks internally consistent.
 *
 * ★THE FAILURE PATH WAS ALREADY HONEST and is deliberately left alone: it keeps the stored summary
 * AND the stored stamp, which agree. Only the success path needed saying. This is why the probe
 * drives BOTH - a fix that stamped "live" unconditionally would satisfy the first direction while
 * making the second one lie.
 *
 * THE ASSERTION:
 *   upgrade succeeds -> the stamp says refreshed live, and no longer says stored
 *   upgrade 429s     -> the stamp still says stored brief, with its generation time
 *
 * Usage: node tools/prove_freshness_stamp_tracks_content.mjs
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
const hasBrief = Number(psql(
  `SELECT count(*) FROM amc_briefings WHERE hive_id='${hive}'
   AND shift_date = timezone('Asia/Manila', now())::date;`)) || 0;
if (!hasBrief) { console.log('SKIP — no brief for today, so there is no stamp to track'); process.exit(0); }

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

  const read = async (succeed) => {
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).slice(0, 100)));
    await page.route('**/functions/v1/analytics-orchestrator*', (r) => (succeed
      ? r.fulfill({ status: 200, contentType: 'application/json',
                    body: JSON.stringify({ action_plan: { headline: 'Live action brief', items: [] } }) })
      : r.fulfill({ status: 429, contentType: 'application/json',
                    body: JSON.stringify({ error: 'AI call limit reached for this hive. Try again in an hour.' }) })));
    await page.goto(`${BASE}/alert-hub.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(11000);
    const out = await page.evaluate(() => {
      const m = document.getElementById('amc-shift-meta');
      const t = (m && m.textContent || '').replace(/\s+/g, ' ').trim();
      return { meta: t.slice(0, 120), saysLive: /refreshed live/i.test(t), saysStored: /stored brief/i.test(t) };
    });
    await page.close();
    return { ...out, errs: errs.length };
  };

  v.upgraded = await read(true);
  v.refused = await read(false);
  console.log(`  upgrade ok  -> ${v.upgraded.meta}`);
  console.log(`  upgrade 429 -> ${v.refused.meta}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 170);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const u = v.upgraded || {}, r = v.refused || {};
const pass = !v.error
  && u.saysLive && !u.saysStored          // fresh content, fresh label
  && r.saysStored && !r.saysLive          // stored content, stored label
  && u.errs === 0 && r.errs === 0;

if (!pass && !v.error) {
  console.log('  A freshness stamp is a claim about the thing beneath it. Leaving "stored brief" over a');
  console.log('  live compose - or stamping "live" over the stored one - makes the label the lie.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — freshness stamp tracks content: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
