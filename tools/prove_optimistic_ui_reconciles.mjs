/**
 * When an optimistic paint's write FAILS, does the UI take it back? (T147, 2026-08-28)
 *
 * T147 could not enumerate optimistic surfaces statically and said so: a sweep for "a paint before
 * an awaited write" returned 78 functions, 67 supposedly without rollback, and the list opened with
 * a colour utility and a label formatter. The true pattern needs a LOCAL STATE MUTATION before the
 * paint, which a regex cannot tell from a render call that merely appears earlier in a function.
 * Its own conclusion was that the right instrument is runtime: fail the write deliberately and
 * watch whether the UI reverts.
 *
 * This is that instrument, and marketplace's watchlist heart is its first subject — identified not
 * by shape but by a behaviour already recorded during T95's walk ("optimistic either way").
 *
 * THREE THINGS MUST ALL HOLD, and they are separable:
 *   1. the paint really is OPTIMISTIC — the heart fills before the server has answered, or there is
 *      nothing here to test and a pass would be vacuous;
 *   2. on failure the paint is TAKEN BACK — the heart returns to its real state;
 *   3. the person is TOLD — a silent rollback is a UI that flickers for no stated reason, which is
 *      its own defect.
 *
 * ★THE NON-VACUITY CHECK IS THE POINT. Asserting only "the heart is empty after a failed write"
 * passes just as happily on a heart that never filled at all — the same shape as a gate that
 * cannot go red. Assertion 1 exists so a future change that quietly drops the optimism cannot slip
 * through as a green.
 *
 * USAGE:  node tools/prove_optimistic_ui_reconciles.mjs
 * Exit 1 on any failed assertion.
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'bryangarcia@auth.workhiveph.com', pw: 'test1234', worker: 'Bryan Garcia' };

const fails = [];
const check = (ok, what, got) => {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${what}${ok ? '' : `  (got: ${got})`}`);
  if (!ok) fails.push(what);
};

console.log('optimistic-ui-reconciles - when the write fails, does the paint come back?\n');

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });

const auth = await ctx.newPage();
await auth.goto(`${BASE}/workhive/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await auth.waitForFunction(() => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
                           { timeout: 20000 }).catch(() => {});
const signedIn = await auth.evaluate(async ({ acct, url }) => {
  try {
    const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
    const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
    const uid = data?.session?.user?.id;
    const { data: m } = uid ? await db.from('hive_members').select('hive_id')
      .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
    if (m?.hive_id) { localStorage.setItem('wh_active_hive_id', m.hive_id); localStorage.setItem('wh_hive_id', m.hive_id); }
    localStorage.setItem('wh_last_worker', acct.worker);
    return !error && !!data?.session;
  } catch (e) { return false; }
}, { acct: ACCT, url: SB_URL });
await auth.close();
if (!signedIn) { console.log('  FAIL  sign-in'); await browser.close(); process.exit(1); }

const page = await ctx.newPage();
// Every watchlist WRITE is refused; reads are left alone so the page still renders normally.
//
// ★THE FAILURE IS DELAYED ON PURPOSE, and the first version of this prover was wrong without it.
// A route handler answers in microseconds — far faster than any real server — so the whole
// optimistic-paint → refusal → rollback cycle completed before the first sample at 150ms, and the
// prover concluded "the paint is not optimistic" about a paint that had already been made and
// taken back. An instrument that outruns the thing it measures reports absence. The delay makes
// the optimistic window real, the way a slow network would.
const FAIL_DELAY_MS = 1500;
await ctx.route('**/rest/v1/marketplace_watchlist*', async (route) => {
  const m = route.request().method();
  if (m === 'POST' || m === 'DELETE' || m === 'PATCH') {
    await new Promise((r) => setTimeout(r, FAIL_DELAY_MS));
    return route.fulfill({ status: 500, contentType: 'application/json',
                           body: JSON.stringify({ message: 'injected watchlist failure' }) });
  }
  return route.continue();
});

await page.goto(`${BASE}/workhive/marketplace.html`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(6000);

const heart = await page.$('.heart-btn[data-listing]');
check(!!heart, 'a watchlist control is reachable to test', 'no .heart-btn[data-listing] on the page');

if (heart) {
  const id = await heart.getAttribute('data-listing');
  const state = () => page.evaluate((lid) => {
    const b = document.querySelector(`.heart-btn[data-listing="${lid}"]`);
    return { saved: !!(b && (b.classList.contains('saved') || b.classList.contains('active'))),
             pressed: b && b.getAttribute('aria-pressed') === 'true' };
  }, id);

  const before = await state();
  // Click WITHOUT awaiting, then read immediately: the optimistic paint happens synchronously,
  // long before the injected 500 comes back.
  await page.evaluate((lid) => document.querySelector(`.heart-btn[data-listing="${lid}"]`).click(), id);
  await page.waitForTimeout(400);   // inside the injected delay window
  const during = await state();
  check(during.saved !== before.saved,
        'the paint IS optimistic (it changes before the server answers)',
        `before=${before.saved} during=${during.saved}`);

  await page.waitForTimeout(FAIL_DELAY_MS + 2500);  // past the refusal + rollback
  const after = await state();
  check(after.saved === before.saved,
        'the failed write is TAKEN BACK (the control returns to its real state)',
        `before=${before.saved} after=${after.saved}`);

  const said = await page.evaluate(() => {
    const t = document.querySelector('#toast, .toast, [role=alert]');
    return t ? (t.innerText || '').replace(/\s+/g, ' ').trim() : '';
  });
  check(/could not|failed|try again|not update/i.test(said),
        'the person is TOLD why the control snapped back', JSON.stringify(said) || '(silent)');
}

await browser.close();
console.log(`\n  ${fails.length ? `FAIL: ${fails.length} assertion(s)`
  : 'PASS: the optimistic paint is real, and a refused write takes it back out loud'}`);
process.exit(fails.length ? 1 : 0);
