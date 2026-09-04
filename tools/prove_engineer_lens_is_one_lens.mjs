/* prove_engineer_lens_is_one_lens.mjs — T52: two switches called Engineer must not contradict.
 *
 * There is no engineer ROLE on this platform: hive_members.role is CHECK-constrained to exactly
 * worker | supervisor. "Engineer" exists twice, as a LENS, in two unrelated places - nav-hub's
 * localStorage 'wh_nav_mode' (all | field | supervisor | engineer), which filters which TOOLS
 * appear, and asset-hub's 'wh_asset_view' (worker | engineer), which decides which PANELS appear.
 *
 * ★INDEPENDENT KEYS, SAME WORD. Someone who picked the Engineer lens in the hub still landed in
 * asset-hub's WORKER view, because an unset wh_asset_view reads as false. They declared themselves
 * once and had to declare it again, with nothing on either surface saying a second switch existed.
 *
 * ★THE FIX IS A DEFAULT, NOT A MERGE. The two scopes really are different - a tool filter is not a
 * panel toggle - and collapsing them would break either the hub's filtering or this page's
 * per-device choice. Only the unset case derives from the hub lens; an explicit toggle here still
 * wins, because the last thing someone did on this page is better evidence than a global lens.
 *
 * THE ASSERTION, four cases, because a fix that simply mirrored the hub would pass the first two
 * and destroy the local toggle:
 *   hub=engineer, no local choice -> engineer   (the defect being fixed)
 *   hub=field,    no local choice -> worker     (no over-reach)
 *   hub=engineer, local=worker    -> worker     (explicit local wins)
 *   hub=field,    local=engineer  -> engineer   (explicit local wins the other way)
 *
 * Usage: node tools/prove_engineer_lens_is_one_lens.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234' };

// asset-hub bounces an unauthenticated visitor before it defines anything, so the lens helper
// simply is not there to ask. The first run of this probe reported noFn four times and looked
// like a broken fix; it was a probe that never reached the page.
const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();
const hive = psql(`SELECT hm.hive_id FROM hive_members hm JOIN auth.users u ON u.id=hm.auth_uid
                   WHERE u.email='${ACCT.email}' AND hm.status='active' LIMIT 1;`).split(/\r?\n/)[0];
if (!hive) { console.log('SKIP — no active hive for the test account'); process.exit(0); }

const CASES = [
  ['hub=engineer, no local choice', { wh_nav_mode: 'engineer' }, true],
  ['hub=field, no local choice', { wh_nav_mode: 'field' }, false],
  ['hub=engineer, local=worker', { wh_nav_mode: 'engineer', wh_asset_view: 'worker' }, false],
  ['hub=field, local=engineer', { wh_nav_mode: 'field', wh_asset_view: 'engineer' }, true],
];

const v = { cases: {} };
const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });

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

  for (const [name, keys, want] of CASES) {
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
    await page.addInitScript((k) => {
      try {
        localStorage.removeItem('wh_asset_view');
        for (const [a, val] of Object.entries(k)) localStorage.setItem(a, val);
      } catch (_) { /* storage blocked; the page falls back to worker either way */ }
    }, keys);
    await page.goto(`${BASE}/asset-hub.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    // ★ASSERT ON WHAT THE PERSON SEES, not on whether a helper exists. The first version asked
    // _assetViewIsEngineer() directly, so against pre-fix code it failed with 'noFn' - the absence
    // of a function, which is a fact about MY patch rather than about the user's experience. The
    // honest oracle is the reliability workbench itself: engineer view shows it, worker view hides
    // it, and that is readable in BOTH worlds.
    // ★AND THE SECOND ORACLE WAS WRONG THE OTHER WAY. The reliability CARD lives inside the asset
    // detail pane, so at page load it is hidden whether the lens says engineer or not - that reading
    // conflates "worker view" with "no asset selected". The toggle BUTTON is the honest signal:
    // _syncAssetView sets its aria-expanded straight from the lens, with no dependency on a
    // selection, and the button exists in the pre-fix world too, so the comparison is real.
    const got = await page.evaluate(() => {
      const btn = document.getElementById('asset-view-toggle');
      if (!btn) return 'noToggle';
      return btn.getAttribute('aria-expanded') === 'true';
    });
    await page.close();
    v.cases[name] = { got, want, ok: got === want, errs: errs.length };
    console.log(`  ${got === want ? 'ok  ' : 'MISS'}  ${name.padEnd(31)} -> ${got} (want ${want})`);
  }
} catch (e) {
  v.error = String(e.message || e).slice(0, 170);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const all = Object.values(v.cases);
const pass = !v.error && all.length === CASES.length
  && all.every((c) => c.ok && c.errs === 0);

if (!pass && !v.error) {
  console.log('  A person who says "I am an engineer" once should not have to say it again on the next');
  console.log('  page, and should not be overruled when they say something different on THIS one.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — engineer lens is one lens: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
