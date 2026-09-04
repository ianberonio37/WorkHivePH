/* prove_old_draft_says_its_age.mjs — T57: a leftover is not an interruption.
 *
 * whAutoSaveDraft is X2 interruption resilience: a worker's typed note survives a phone call, an
 * app switch, a dead battery. It is careful work - it refuses a draft belonging to another worker
 * (the shared-device leak), it detects an untouched SELECT by its default rather than by emptiness
 * (the "Critical" urgency that silently reverted to "Normal"), and it now says where drafts live.
 *
 * ★BUT IT CARRIED NO AGE. A draft typed three months ago restored into the form exactly like one
 * typed three minutes ago: silently, into fields the worker is about to submit. On a logbook entry
 * that means filing a stale reading against today's shift, with nothing having said the text was
 * old. Interruption resilience is measured in minutes and hours; a draft that survives a WEEK has
 * stopped being an interruption and become a leftover.
 *
 * ★IT SAYS THE AGE RATHER THAN DISCARDING THE TEXT. The work is still the worker's to keep or
 * clear, and throwing away a note because it is old would be the opposite failure - X2 exists
 * precisely so typed work is never lost.
 *
 * THE ASSERTION, four ages, because a notice that always fired would be noise and one that never
 * fired would be the bug:
 *   0 days  -> restored, silent          (the feature working normally)
 *   6 days  -> restored, silent          (still inside the interruption window)
 *   8 days  -> restored, says "8 days old"
 *   90 days -> restored, says "90 days old"
 *
 * ★THE PROBE MUST SIGN IN. The draft's owner check compares against wh_last_worker; unauthenticated,
 * logbook redirects to index and the owner reads null, so the draft is correctly refused and nothing
 * restores. An earlier run reported restored:false four times and looked like a broken fix.
 *
 * Usage: node tools/prove_old_draft_says_its_age.mjs
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
                   WHERE u.email='${ACCT.email}' AND hm.status='active' LIMIT 1;`).split(/\r?\n/)[0];
if (!hive) { console.log('SKIP — no active hive for the test account'); process.exit(0); }

const CASES = [
  ['fresh (0d)', 0, false],
  ['inside the window (6d)', 6, false],
  ['just past it (8d)', 8, true],
  ['long forgotten (90d)', 90, true],
];

const v = { cases: {} };
const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });

  const auth = await ctx.newPage();
  await auth.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await auth.waitForFunction(
    () => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
    { timeout: 20000 }).catch(() => {});
  const signedIn = await auth.evaluate(async ({ acct, url, hiveId }) => {
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
  if (!signedIn) throw new Error('sign-in failed');

  for (const [name, ageDays, want] of CASES) {
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
    await page.goto(`${BASE}/logbook.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    const res = await page.evaluate(({ days }) => {
      const inp = document.createElement('input');
      inp.id = 'wh-t57-probe-input';
      document.body.appendChild(inp);
      const K = 'wh_view_' + (location.pathname.split('/').pop() || 'root') + '_draft_wh_t57_probe';
      localStorage.setItem(K, JSON.stringify({
        __owner: (localStorage.getItem('wh_last_worker') || ''),
        // __hive rides the stamp since the hive-scoped-drafts hardening: a draft whose hive
        // does not match the CURRENT hive is refused like an ownerless one. Seed it the way
        // the product stamps it (whHiveId), or every case reads restored:false — which is
        // exactly how this probe went red on 2026-09-03.
        __hive: String((typeof whHiveId === 'function' ? whHiveId() : null) || ''),
        __savedAt: Date.now() - days * 86400000,
        'wh-t57-probe-input': 'a note typed a while ago',
      }));
      const seen = [];
      const real = window.showToast;
      window.showToast = (m) => seen.push(String(m));
      window.whAutoSaveDraft('wh_t57_probe', ['wh-t57-probe-input']);
      window.showToast = real;
      try { localStorage.removeItem(K); } catch (_) { /* probe key, best effort */ }
      return { restored: !!inp.value, seen };
    }, { days: ageDays });
    await page.close();
    const said = res.seen.some((m) => /days old/.test(m));
    v.cases[name] = { restored: res.restored, saidAge: said, want, ok: res.restored && said === want,
                      errs: errs.length };
    console.log(`  ${res.restored && said === want ? 'ok  ' : 'MISS'}  ${name.padEnd(24)} restored=${res.restored} saysAge=${said} (want ${want})`);
  }
} catch (e) {
  v.error = String(e.message || e).slice(0, 170);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const all = Object.values(v.cases);
const pass = !v.error && all.length === CASES.length && all.every((c) => c.ok && c.errs === 0);
if (!pass && !v.error) {
  console.log('  A months-old draft that fills the form silently invites a stale entry against today\'s');
  console.log('  shift. Keep the text - it is the worker\'s - but say how old it is.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — old draft says its age: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
