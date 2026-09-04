/* prove_fab_anchor_stable.mjs — T184: the one control that must never move (2026-08-26).
 *
 * The nav-hub FAB is on every page, in the same corner, and it is the platform's single piece of
 * muscle memory: a worker's thumb goes there without looking. Every other inconsistency between
 * 24 pages costs a moment of thought; this one costs a MISSED TAP, over and over, on the control
 * that exists to get you out of wherever you are.
 *
 * MEASURED AT 390: x = 303, 312 and 318 across eight pages - a 15px spread - while every page had an
 * identical `#wh-hub { right: 16px }` and an identical 56px FAB. The cause was not in any page's hub
 * styling, and three hypotheses were wrong before the measurement settled it:
 *   "a scrollbar is narrowing the viewport"  - refuted: innerWidth - clientWidth was 0 everywhere.
 *   "an ancestor transform is creating a containing block" - refuted: the hub is a child of BODY on
 *      every page and no ancestor carried transform/filter/contain/will-change.
 *   "inventory sets scrollbar-width: thin"   - refuted: no such declaration exists there.
 * What settled it was a virgin `position: fixed; right: 0; width: 0` probe, which reports where the
 * containing block's right edge ACTUALLY is: 375 on community, 384 on inventory, 390 on logbook -
 * while documentElement.clientWidth read 390 on all three, which is exactly why nothing in the DOM
 * revealed it. A fixed right-anchored element is measured from the SCROLLPORT, and the RESERVED
 * GUTTER narrows it whether or not a bar is drawn. The spread was the cross-product of two unrelated
 * per-page CSS decisions - `html { scrollbar-gutter: stable }` (components.css:231, linked by some
 * pages) and `::-webkit-scrollbar { width: 6px }` (declared inline by others): reserve 15px -> 303,
 * 6px -> 312, nothing -> 318. Neither was ever made with the FAB in mind.
 * FIXED at the altitude that owns the stack: nav-hub.js injects both halves on every page, beside
 * the reserve and lift rules that already live there for the same reason. Spread is now 0.
 *
 * ★y IS DELIBERATELY NOT REQUIRED TO MATCH, and that distinction is the finding. The FAB stack is
 * lifted by --wh-fab-lift on pages carrying a fixed bottom element, so the hub clears it (V1
 * no-collision, nav-hub.js:1242). A page whose FAB rides higher is not drifting - it is avoiding a
 * collision, and forcing it down would put the hub ON TOP of that page's own bottom bar. So this
 * prover asserts x (which has no legitimate reason to vary) and REPORTS y with its lift, rather
 * than failing a page for doing the right thing.
 *
 * Usage: node tools/prove_fab_anchor_stable.mjs
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234',
               worker: 'Leandro Marquez', hiveName: 'Baguio Textile Mills' };

const PAGES = ['logbook.html', 'pm-scheduler.html', 'community.html', 'inventory.html',
               'asset-hub.html', 'alert-hub.html', 'index.html', 'analytics.html'];

const browser = await chromium.launch();
const rows = [];
let fatal = null;
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const auth = await ctx.newPage();
  await auth.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await auth.waitForFunction(
    () => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
    { timeout: 20000 }).catch(() => {});
  const ok = await auth.evaluate(async ({ acct, url }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
      const uid = data?.session?.user?.id;
      const { data: m } = uid ? await db.from('hive_members').select('hive_id')
        .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
      if (m?.hive_id) {
        localStorage.setItem('wh_active_hive_id', m.hive_id);
        localStorage.setItem('wh_hive_id', m.hive_id);
      }
      localStorage.setItem('wh_last_worker', acct.worker);
      localStorage.setItem('wh_hive_name', acct.hiveName);
      localStorage.setItem('wh_hive_role', 'supervisor');
      return !error && !!data?.session;
    } catch (e) { return false; }
  }, { acct: ACCT, url: SB_URL });
  await auth.close();
  if (!ok) throw new Error('sign-in failed — the FAB only mounts for a signed-in user');

  for (const pg of PAGES) {
    const page = await ctx.newPage();
    // the gutter rule ships from nav-hub.js, a file on all 24 pages - so a regression here can be a
    // script that stopped running, not only a rule that changed. Collect errors per page.
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
    await page.goto(`${BASE}/${pg}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(5500);
    const r = await page.evaluate(() => {
      const f = document.getElementById('wh-hub-fab');
      if (!f) return { absent: true };
      const b = f.getBoundingClientRect();
      return {
        x: Math.round(b.left), y: Math.round(b.top),
        gutter: getComputedStyle(document.documentElement).scrollbarGutter,
        lift: getComputedStyle(document.documentElement).getPropertyValue('--wh-fab-lift').trim() || '0px',
        scrollbarPx: window.innerWidth - document.documentElement.clientWidth,
      };
    });
    await page.close();
    rows.push({ page: pg, ...r, pageerrors: errs.length });
    console.log(`  ${pg.padEnd(20)} x=${r.absent ? 'ABSENT' : r.x} y=${r.y ?? '-'} `
      + `gutter=${r.gutter ?? '-'} lift=${r.lift ?? '-'} err=${errs.length}`
      + (errs.length ? ' :: ' + errs[0] : ''));
  }
} catch (e) {
  fatal = String(e.message || e).slice(0, 160);
  console.log('probe error:', fatal);
} finally {
  await browser.close();
}

const seen = rows.filter((r) => !r.absent);
const absent = rows.filter((r) => r.absent).map((r) => r.page);
const xs = [...new Set(seen.map((r) => r.x))];
const spread = xs.length ? Math.max(...xs) - Math.min(...xs) : 0;
const noGutter = seen.filter((r) => r.gutter !== 'stable').map((r) => `${r.page} (${r.gutter})`);

console.log(`  x values: ${xs.sort((a, b) => a - b).join(', ')} | spread ${spread}px`
  + ` | pages without a stable gutter: ${noGutter.length}`);
const broken = seen.filter((r) => r.pageerrors > 0).map((r) => `${r.page}(${r.pageerrors})`);
const pass = !fatal && seen.length === PAGES.length && spread === 0 && noGutter.length === 0
  && broken.length === 0;
if (broken.length) console.log(`  pages throwing at runtime: ${broken.join(', ')}`);
if (!pass) {
  if (absent.length) console.log(`  FAB absent on: ${absent.join(', ')}`);
  if (spread) console.log(`  The FAB sits in ${xs.length} different columns. A fixed right-anchored`
    + ` element is measured from the SCROLLPORT, which the RESERVED GUTTER narrows whether or not a`
    + ` bar is drawn - so check scrollbar-gutter AND the scrollbar's width together, not the hub CSS.`);
  if (noGutter.length) console.log(`  Missing 'scrollbar-gutter: stable' (components.css:231): `
    + noGutter.join(', '));
}
console.log((pass ? 'PASS' : 'FAIL') + ` — FAB anchor: ${JSON.stringify({ pages: seen.length, spread, noGutter: noGutter.length, pageerrors: broken.length, fatal })}`);
process.exit(pass ? 0 : 1);
