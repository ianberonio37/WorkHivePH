/* prove_waiting_is_spoken.mjs — T181: waiting must SAY it is waiting (2026-08-26).
 *
 * A page that fetches its content leaves a gap between paint and data. What fills that gap is the
 * whole question. A skeleton or a "Loading…" line says "wait"; an EMPTY region says "there is
 * nothing here", and the reader acts on that - they leave, or they re-tap, or they file a bug about
 * missing data that arrives 200ms after they looked away.
 *
 * ★THIS MEASURES THE EXPERIENCE, NOT THE VOCABULARY, AND THAT NARROWING IS DELIBERATE. T181's census
 * found skeletons and spinners coexisting across pages and called waiting "not yet one product's
 * language". True - but which metaphor a page picks is a design judgement, and a gate that fails a
 * page for choosing a spinner over a skeleton would be enforcing taste across 24 pages and producing
 * dozens of arguable findings. What is NOT a matter of taste: whether the gap says anything at all.
 * So this asserts the floor - during the load window, the main region is not silently blank - and
 * REPORTS which idiom each page uses, so the vocabulary question stays visible without being
 * enforced by a machine.
 *
 * Sampled early (before data can plausibly have arrived) and again after settle, so a page that
 * paints instantly from cache is not failed for having no gap to fill.
 *
 * Usage: node tools/prove_waiting_is_spoken.mjs
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234',
               worker: 'Leandro Marquez', hiveName: 'Baguio Textile Mills' };

const PAGES = ['logbook.html', 'inventory.html', 'community.html', 'asset-hub.html',
               'alert-hub.html', 'analytics.html', 'marketplace.html', 'pm-scheduler.html'];

const SAMPLE = () => {
  const root = document.querySelector('main') || document.getElementById('root') || document.body;
  const txt = (root.innerText || '').trim();
  const sk = document.querySelectorAll(
    '.skeleton, .skeleton-card, [class*="skeleton"], .wh-skeleton').length;
  const sp = document.querySelectorAll(
    '.spinner, .loader, [class*="spinner"], [class*="loading"]').length;
  const says = /loading|loading…|please wait|fetching/i.test(txt);
  return { chars: txt.length, skeletons: sk, spinners: sp, saysLoading: says };
};

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
  if (!ok) throw new Error('sign-in failed');

  for (const pg of PAGES) {
    const page = await ctx.newPage();
    // throttle so the gap is real and observable rather than a race we usually lose
    await page.route('**/rest/v1/**', async (route) => {
      await new Promise((r) => setTimeout(r, 1200));
      await route.continue();
    });
    await page.goto(`${BASE}/${pg}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    const during = await page.evaluate(SAMPLE);
    await page.waitForTimeout(6000);
    const after = await page.evaluate(SAMPLE);
    await page.close();

    const idiom = during.skeletons ? 'skeleton'
      : during.saysLoading ? 'loading-text'
        : during.spinners ? 'spinner' : 'NOTHING';
    // ★THE FIRST VERSION OF THIS LINE READ `during.chars < 120`, AND IT WAS THE WRONG INSTRUMENT.
    // Teeth-testing it by stripping inventory's "Loading..." lines produced idiom=NOTHING and a PASS,
    // because the page still rendered 389 characters of CHROME - headings, nav, tile labels - while
    // the region a reader was actually waiting on sat empty. An absolute threshold over the whole
    // main region measures the furniture, not the gap. GROWTH is the honest signal: if substantial
    // content arrived later and nothing marked the wait, the reader was shown a finished-looking
    // page that was not finished.
    const grew = after.chars - during.chars;
    const silent = idiom === 'NOTHING' && grew > 300;
    rows.push({ page: pg, idiom, silent, during, after });
    console.log(`  ${pg.padEnd(20)} during: ${String(during.chars).padStart(5)} chars, `
      + `sk=${during.skeletons} sp=${during.spinners} text=${during.saysLoading} `
      + `-> ${idiom}${silent ? '  <-- SILENT GAP' : ''} (settled ${after.chars})`);
  }
} catch (e) {
  fatal = String(e.message || e).slice(0, 160);
  console.log('probe error:', fatal);
} finally {
  await browser.close();
}

const silent = rows.filter((r) => r.silent).map((r) => r.page);
const idioms = rows.reduce((a, r) => { a[r.idiom] = (a[r.idiom] || 0) + 1; return a; }, {});
console.log(`  idioms in use: ${JSON.stringify(idioms)}`);
const pass = !fatal && rows.length === PAGES.length && silent.length === 0;
if (silent.length) {
  console.log(`  ${silent.length} page(s) show a blank region while loading: ${silent.join(', ')}`);
  console.log('  An empty region does not read as "wait", it reads as "nothing here".');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — waiting is spoken: ${JSON.stringify({ pages: rows.length, silent: silent.length, idioms, fatal })}`);
process.exit(pass ? 0 : 1);
