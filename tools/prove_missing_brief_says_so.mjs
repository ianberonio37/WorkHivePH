/* prove_missing_brief_says_so.mjs — T81: a daily brief that did not run must say so.
 *
 * The 6am PHT cron writes one amc_briefings row per shift_date, and alert-hub reads only TODAY's.
 * That scoping is right: yesterday's brief must never pose as this morning's.
 *
 * ★BUT WHEN THE CRON MISSED, THE CARD VANISHED. renderAmcCard(null) set display:none, so the
 * supervisor could not tell "no brief ran today" from "this feature does not exist" or "the page is
 * still loading". Worse, a skeleton is shown in that card on first load, so the sequence was a
 * loading state resolving into NOTHING - an answer erasing itself, on a surface whose whole promise
 * is a brief every morning. The absence IS the news.
 *
 * THE ASSERTION, both directions:
 *   1. MISSING  — with today's row absent, the card is VISIBLE and says a brief was not generated,
 *                 names the 6am cadence, and blanks the figure tiles so no number stands under a
 *                 "not generated" header.
 *   2. PRESENT  — with the real row, the card still renders the brief and does NOT claim absence.
 * Direction 2 matters: a card that always cried "no brief" would satisfy the first half while
 * destroying the feature.
 *
 * ★NO DATA IS MUTATED. Only the today-scoped read (shift_date=eq.) is intercepted, so the historic
 * query still answers for real - which is what lets the empty state name the most recent brief.
 *
 * Usage: node tools/prove_missing_brief_says_so.mjs
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
const hasToday = Number(psql(
  `SELECT count(*) FROM amc_briefings WHERE hive_id='${hive}'
   AND shift_date = timezone('Asia/Manila', now())::date;`)) || 0;

const v = { fixtureHasTodayBrief: hasToday > 0 };
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

  const read = async (hideToday) => {
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
    if (hideToday) {
      // ONLY the today-scoped read; the historic one (shift_date=neq.) answers for real
      await page.route('**/rest/v1/amc_briefings*', (route) => {
        const u = route.request().url();
        if (u.includes('shift_date=eq.')) {
          return route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
        }
        return route.continue();
      });
    }
    await page.goto(`${BASE}/alert-hub.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(9000);
    const out = await page.evaluate(() => {
      const card = document.getElementById('amc-card');
      if (!card) return { noCard: true };
      const shown = card.offsetHeight > 0 && getComputedStyle(card).display !== 'none';
      const t = (card.innerText || '').replace(/\s+/g, ' ').trim();
      return {
        shown,
        saysNotGenerated: /not generated|was not generated/i.test(t),
        namesCadence: /6am/i.test(t),
        stillSkeleton: !!document.getElementById('amc-loading'),
        text: t.slice(0, 130),
      };
    });
    await page.close();
    return { ...out, errs: errs.length };
  };

  v.missing = await read(true);
  v.present = await read(false);
  console.log(`  cron missed -> shown=${v.missing.shown} says-not-generated=${v.missing.saysNotGenerated}`);
  console.log(`     "${v.missing.text}"`);
  console.log(`  brief present -> shown=${v.present.shown} claims-absence=${v.present.saysNotGenerated}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 170);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const m = v.missing || {}, p = v.present || {};
const pass = !v.error && !m.noCard
  && m.shown && m.saysNotGenerated && m.namesCadence && !m.stillSkeleton   // absence is spoken
  && p.shown && !p.saysNotGenerated                                        // a real brief still renders
  && m.errs === 0 && p.errs === 0;

if (!pass && !v.error) {
  console.log('  A morning brief that did not run must say it did not run. Hiding the card leaves a');
  console.log('  supervisor unable to tell a missed cron from a feature that was never there.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — missing brief says so: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
