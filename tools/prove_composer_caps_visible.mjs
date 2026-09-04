/* prove_composer_caps_visible.mjs — T168: a cap must announce itself (2026-08-26).
 *
 * A maxlength with no counter is a SILENT WALL. The textarea simply stops accepting
 * keystrokes, and the person typing does not read that as "you reached 1000 characters" -
 * they read it as a broken keyboard, or a broken app, and they lose the thought they were
 * mid-way through writing. The guard is correct; the silence is the defect.
 *
 * FOUND ON community.html, which had built the right pattern and applied it unevenly: the
 * post composer (2000) and the report box (500) each carry a live "n / max" counter, and the
 * reply box (1000) carried none. One page, three composers, two of them honest.
 *
 * ★THE STATIC SCAN THAT FOUND IT WAS WRONG TWICE FIRST and its errors are why this probe is
 * LIVE. Guessing the counter's id from the field's id ("<id>-char-count") reported #post-content
 * as uncounted - its counter is #post-char-count. Only reading the RENDERED page settles which
 * fields tell the truth, because a counter is whatever visible element moves when you type.
 *
 * WHAT IT ASSERTS, for each composer on the page:
 *   counts    typing raises a visible element that shows the length and the cap
 *   resets    posting/reopening returns it to 0 - a counter stuck at the last message's length
 *             is a stale reading, which is worse than none
 *
 * Usage: node tools/prove_composer_caps_visible.mjs
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234',
               worker: 'Leandro Marquez', hiveName: 'Baguio Textile Mills' };

const FIELDS = [
  { field: 'post-content', counter: 'post-char-count', cap: 2000 },
  { field: 'reply-content', counter: 'reply-char-count', cap: 1000 },
  { field: 'report-details', counter: 'report-char-count', cap: 500 },
];

const browser = await chromium.launch();
const v = { checked: 0, silent: [], stale: [], pageerrors: 0 };
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });

  // sign in on a light page first (the live_page_journeys shape)
  const auth = await ctx.newPage();
  await auth.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await auth.waitForFunction(() => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
    { timeout: 20000 }).catch(() => {});
  const signedIn = await auth.evaluate(async ({ acct, url }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
      const uid = data?.session?.user?.id;
      const { data: mem } = uid ? await db.from('hive_members').select('hive_id')
        .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
      if (mem?.hive_id) {
        localStorage.setItem('wh_active_hive_id', mem.hive_id);
        localStorage.setItem('wh_hive_id', mem.hive_id);
      }
      localStorage.setItem('wh_last_worker', acct.worker);
      localStorage.setItem('wh_hive_name', acct.hiveName);
      localStorage.setItem('wh_hive_role', 'supervisor');
      return !error && !!data?.session;
    } catch (e) { return false; }
  }, { acct: ACCT, url: SB_URL });
  await auth.close();
  v.signedIn = signedIn;
  if (!signedIn) throw new Error('sign-in failed — cannot reach the signed-in composers');

  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e).slice(0, 100)));
  await page.goto(`${BASE}/community.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);

  // the reply box and report box live inside overlays — the counter must exist and be wired
  // whether or not its overlay is open, so this reads the wiring, then types into each field.
  for (const f of FIELDS) {
    const r = await page.evaluate(({ field, counter, cap }) => {
      const ta = document.getElementById(field);
      const el = document.getElementById(counter);
      if (!ta || !el) return { missing: !ta ? 'field' : 'counter' };
      const before = el.textContent.trim();
      ta.value = 'x'.repeat(37);
      ta.dispatchEvent(new Event('input', { bubbles: true }));
      const after = el.textContent.trim();
      // reset path: clear and fire again
      ta.value = '';
      ta.dispatchEvent(new Event('input', { bubbles: true }));
      const cleared = el.textContent.trim();
      return { before, after, cleared, capShown: after.includes(String(cap)), moved: after !== before };
    }, f);
    v.checked += 1;
    if (r.missing) { v.silent.push(`${f.field}: no ${r.missing}`); continue; }
    if (!r.moved || !r.capShown) v.silent.push(`${f.field}: counter did not report "37 / ${f.cap}" (saw "${r.after}")`);
    if (r.cleared !== `0 / ${f.cap}`) v.stale.push(`${f.field}: after clearing, counter reads "${r.cleared}"`);
    console.log(`  ${f.field}: typed 37 -> "${r.after}" | cleared -> "${r.cleared}"`);
  }
  v.pageerrors = errs.length;
  if (errs.length) console.log('  pageerrors:', errs.join(' | '));
} catch (e) {
  v.error = String(e.message || e).slice(0, 160);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const pass = !v.error && v.checked === FIELDS.length && !v.silent.length && !v.stale.length
  && v.pageerrors === 0;
if (v.silent.length) console.log('  SILENT:', v.silent.join(' | '));
if (v.stale.length) console.log('  STALE:', v.stale.join(' | '));
console.log((pass ? 'PASS' : 'FAIL') + ` — composer caps visible: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
