/* ============================================================================
 * arc_x_continuity_sweep.mjs — Arc X (Cognitive Load II) LIVE continuity harness
 * ============================================================================
 * The RUNTIME proof for Family-A continuity types that a static gate can't see:
 *   A3 (list-state persistence) — load `<page>?q=<term>` => the search input must
 *       RESTORE the term (URL -> control), AND typing a new term must MIRROR back
 *       to the URL (control -> URL via replaceState). Both directions = the filter
 *       survives a reload / leave-and-back-nav (the Issue-#2-cousin: don't make the
 *       user re-type the filter on every hand-off).
 *
 * Complements the STATIC presence-guards in validate_arc_x_cognitive.py
 * (a3_state_persistence) with a real browser round-trip, so an A3 regression that
 * keeps the `_*SyncUrl` symbol but breaks the behaviour is still caught.
 *
 * Usage:  node tools/arc_x_continuity_sweep.mjs
 * Exit 0 = every surface round-trips; exit 1 = a continuity break.
 * Reuses the live_page_journeys sign-in shape (real Supabase session + hive keys).
 * ==========================================================================*/
import { chromium } from 'playwright';

const BASE   = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL  || 'http://127.0.0.1:54321';
const HIVE   = process.env.WH_TEST_HIVE     || '636cf7e8-431a-4907-8a9f-43dd4cc216d6'; // hive fallback only — signIn resolves the real hive from the live membership
const ACCT   = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234', worker: 'Leandro Marquez', hiveName: 'Baguio Textile Mills' };

// A3 surfaces that filter a browse-list via a `#search-input` mirrored to `?q=`.
// `mineView`: logbook's URL-mirror is scoped to the "mine" view BY DESIGN (the team
// view searches server-side and is intentionally not mirrored) - so pin mine-view
// before the mirror check, or we'd test a view where mirroring is correctly off.
const SURFACES = [
  { page: 'inventory.html',   term: 'bearing' },
  { page: 'logbook.html',     term: 'pump', mineView: true },
  { page: 'marketplace.html', term: 'motor' },
  { page: 'community.html',   term: 'safety' },
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function signIn(context) {
  const page = await context.newPage();
  await page.goto(`${BASE}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => typeof window.getDb === 'function' && !!window.SUPABASE_KEY, { timeout: 15000 }).catch(() => {});
  const r = await page.evaluate(async ({ acct, hive, url }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
      // resolve the REAL hive from the live membership (test_identity pattern) — the passed
      // constant rots across reseeds (636cf7e8 was deleted); it is only the fallback.
      let realHive = hive;
      try {
        const uid = data?.session?.user?.id;
        const { data: mem } = uid ? await db.from('hive_members').select('hive_id')
          .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
        if (mem && mem.hive_id) realHive = mem.hive_id;
      } catch (_) { /* keep fallback */ }
      localStorage.setItem('wh_active_hive_id', realHive);
      localStorage.setItem('wh_hive_id', realHive);
      localStorage.setItem('wh_last_worker', acct.worker);
      localStorage.setItem('wh_hive_name', acct.hiveName);
      localStorage.setItem('wh_hive_role', 'supervisor');
      localStorage.setItem('wh_nav_mode', 'supervisor');
      return { ok: !error && !!data?.session };
    } catch (e) { return { ok: false, err: String(e) }; }
  }, { acct: ACCT, hive: HIVE, url: SB_URL });
  await page.close();
  return r;
}

async function probe(context, surf) {
  const page = await context.newPage();
  const defects = [];
  try {
    // ---- RESTORE direction: URL ?q= -> the search input shows the term ----
    await page.goto(`${BASE}/workhive/${surf.page}?q=${encodeURIComponent(surf.term)}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#search-input', { timeout: 12000 }).catch(() => {});
    await sleep(1800);
    const restored = await page.$eval('#search-input', (el) => el.value).catch(() => null);
    if ((restored || '').toLowerCase() !== surf.term.toLowerCase()) {
      defects.push(`${surf.page}: A3 RESTORE failed — ?q=${surf.term} did not repopulate #search-input (got ${JSON.stringify(restored)})`);
    }
    // ---- MIRROR direction: typing a new term -> the URL ?q= updates ----
    // pin the view that owns the URL mirror where the surface scopes it (logbook).
    if (surf.mineView) {
      await page.evaluate(() => { if (typeof window.setViewMode === 'function') window.setViewMode('mine'); }).catch(() => {});
      await sleep(400);
    }
    const term2 = surf.term.slice(0, 3) + 'x';
    await page.fill('#search-input', term2).catch(() => {});
    await page.dispatchEvent('#search-input', 'input').catch(() => {});
    await sleep(1200);
    const url = new URL(page.url());
    if ((url.searchParams.get('q') || '').toLowerCase() !== term2.toLowerCase()) {
      defects.push(`${surf.page}: A3 MIRROR failed — typing "${term2}" did not update ?q= (url q=${JSON.stringify(url.searchParams.get('q'))})`);
    }
  } catch (e) {
    defects.push(`${surf.page}: probe error ${String(e).slice(0, 120)}`);
  } finally {
    await page.close();
  }
  return defects;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const si = await signIn(context);
  if (!si.ok) { console.error('sign-in failed:', si); await browser.close(); process.exit(2); }

  console.log('\nArc X — LIVE continuity sweep (A3 list-state round-trip)');
  console.log('='.repeat(60));
  let allDefects = [];
  for (const surf of SURFACES) {
    const d = await probe(context, surf);
    console.log(`  ${d.length ? 'FAIL' : 'PASS'}  ${surf.page.padEnd(20)} (?q=${surf.term})`);
    allDefects = allDefects.concat(d);
  }
  await browser.close();

  if (allDefects.length) {
    console.log(`\n  ${allDefects.length} continuity defect(s):`);
    allDefects.forEach((d) => console.log('   - ' + d));
    process.exit(1);
  }
  console.log(`\n  PASS — all ${SURFACES.length} A3 surfaces round-trip (URL<->filter both directions).`);
  process.exit(0);
})();
