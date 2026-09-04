/**
 * prove_seller_dashboard_is_reachable.mjs - T55/T78: can a person actually GET there? (2026-08-28)
 *
 * Both fixes this proves were made statically, by reading a registry and a filter. That is enough
 * to know the code changed and NOT enough to know a person can reach the page, which is the only
 * claim that matters - so this drives the real hub and the real search overlay in a browser.
 *
 * WHAT WAS BROKEN:
 *   1. marketplace-seller.html - a seller's own dashboard, and for a supplier persona their whole
 *      platform - had NO entry in nav-hub's TOOLS registry. Not `hidden: true`; ABSENT. So it was
 *      missing from the All Tools grid AND unfindable by search, because search-overlay reads that
 *      same registry. The only route was remembering to open Marketplace and spotting a pill.
 *   2. search-overlay filtered `!t.hidden`, so the four curated-out pages - Audit Log, AI Quality,
 *      PH Intelligence, Project Report - could not be reached by typing their own names from
 *      anywhere on the platform. Audit Log is the sharp one: an audit trail nobody can navigate to
 *      is write-only, and the whole point of it is the moment someone needs it and does not
 *      already know the route.
 *
 * ★THE ASSERTIONS ARE DELIBERATELY ABOUT REACHABILITY, NOT MARKUP. Checking that the registry
 * array contains a string would re-test what the static fix already guaranteed and would pass just
 * as happily if the grid never rendered or the search never opened. So each check drives the UI a
 * person drives, and reads what a person would see.
 *
 * Usage: node tools/prove_seller_dashboard_is_reachable.mjs
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

console.log('seller-dashboard-is-reachable - the nav spine and the search, driven as a person\n');

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
await page.goto(`${BASE}/workhive/logbook.html`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#wh-hub-fab', { timeout: 20000 });

// ── 1. the All Tools grid ────────────────────────────────────────────────────────────────────
await page.click('#wh-hub-fab');
await page.waitForSelector('#wh-hub-panel', { state: 'visible', timeout: 8000 }).catch(() => {});
await page.waitForTimeout(400);

// Read the LINK a person would click, not the registry behind it.
const grid = await page.evaluate(() => {
  const panel = document.getElementById('wh-hub-panel');
  if (!panel) return { open: false, links: [] };
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  };
  return {
    open: vis(panel),
    links: [...panel.querySelectorAll('a[href]')].filter(vis)
      .map(a => ({ href: a.getAttribute('href'), text: (a.innerText || '').replace(/\s+/g, ' ').trim() })),
  };
});
check(grid.open, 'the hub panel opens', 'panel not visible');

/* ★THE GRID IS NOT WHERE THIS PAGE LIVES, AND THAT IS DELIBERATE. Registering it as a visible
   entry pushed the home-stack budget over for two roles at once (field 14/13, supervisor 21/20) -
   both were AT budget, because the cap protects how many choices a primary nav puts in front of a
   person, and a seller's dashboard is not a daily tool for a plant worker. So it is registered
   `hidden: true`: off the grid, still indexed by search. The assertion therefore checks that the
   grid stays WITHIN its budget rather than that this entry appears in it - asserting the entry
   were visible would be asserting a regression of the cognitive-load cap. */
const audit_ = grid.links.filter(l => (l.href || '').includes('marketplace-seller.html'));
check(audit_.length === 0, 'the seller dashboard is NOT taking a primary-nav slot (hidden by design)',
      `${audit_.length} grid link(s) to it`);

// ── 2. the global search ─────────────────────────────────────────────────────────────────────
async function search(term) {
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(200);
  // Ctrl+K is the documented user path (search-overlay registers it once at module load), so the
  // probe uses the shortcut a person uses and only falls back to the public API if that fails.
  await page.keyboard.press('Control+K');
  let ready = await page.waitForSelector('#ws-input', { state: 'visible', timeout: 5000 })
    .then(() => true).catch(() => false);
  if (!ready) {
    const opened = await page.evaluate(() => {
      if (window.WHSearch && typeof window.WHSearch.open === 'function') { window.WHSearch.open(); return true; }
      return false;
    });
    if (!opened) return null;
    ready = await page.waitForSelector('#ws-input', { state: 'visible', timeout: 5000 })
      .then(() => true).catch(() => false);
  }
  if (!ready) return null;
  await page.fill('#ws-input', '');
  await page.type('#ws-input', term, { delay: 20 });
  await page.waitForTimeout(700);
  return page.evaluate(() => {
    const r = document.getElementById('ws-results');
    if (!r) return [];
    return [...r.querySelectorAll('a[href]')].map(a => ({
      href: a.getAttribute('href'), text: (a.innerText || '').replace(/\s+/g, ' ').trim(),
    }));
  });
}

const audit = await search('audit log');
if (audit === null) {
  check(false, 'the search overlay can be opened', 'no opener found');
} else {
  check(audit.some(r => (r.href || '').includes('audit-log.html')),
        'searching "audit log" reaches the audit trail (a hidden page)',
        audit.map(r => r.href).join(', ') || 'no results');
}

const seller = await search('seller');
if (seller) {
  check(seller.some(r => (r.href || '').includes('marketplace-seller.html')),
        'searching "seller" reaches the seller dashboard',
        seller.map(r => r.href).join(', ') || 'no results');
}

await browser.close();
console.log('');
if (fails.length) {
  console.log(`FAIL seller-dashboard-is-reachable - ${fails.length} reachability check(s) failed`);
  process.exit(1);
}
console.log('PASS seller-dashboard-is-reachable - curated OUT of the primary nav to protect its budget, '
          + 'and reachable by name through search, driven live.');
