/* prove_cold_page_teaches.mjs — T175: every page introduces itself to a first-time reader (2026-08-26).
 *
 * A brand-new account has no assets, no PMs, no history. Every list on every page is empty, and an
 * empty page has exactly one job: say what this page is FOR and what the first action is. Get that
 * wrong and the reader concludes the product is broken or not for them - on their first visit, which
 * is the only one they are guaranteed to make.
 *
 * ★THE PREVIOUS PASS OF THIS SWEEP SCORED TWO PAGES WRONG, IN BOTH DIRECTIONS, and this probe is
 * shaped by those errors:
 *   - It read a 320-CHARACTER SLICE of the body, which truncated ABOVE analytics' teaching block, so
 *     a page that does teach ("Not enough data yet - log corrective failures + run a few PM
 *     completions, then come back") was recorded as silent. This one reads the WHOLE region.
 *   - It matched a narrow teach-REGEX, which missed "Choose Your Primary Discipline" and "team tool"
 *     because those are not the words the regex expected. So this one does NOT grade with a regex:
 *     it captures the text and reports it, flagging only a region that is genuinely EMPTY. A human
 *     reads the captures and judges. An oracle that decides whether prose teaches is an oracle that
 *     will be wrong about prose.
 *
 * The account is created through the PUBLIC signup path (the real cold experience), marked, and
 * deleted afterwards - and because every personal table CASCADEs from auth.users (see
 * erasure-path-intact), deleting the user takes its rows with it. Residue is re-counted.
 *
 * Usage: node tools/prove_cold_page_teaches.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const MARK = 'wh-t175-probe';
const EMAIL = `${MARK}@auth.workhiveph.com`;
const PW = 'test1234!Probe';

// the 19 not covered by the 2026-08-25 pass (which did logbook, pm-scheduler, inventory,
// skillmatrix, analytics). Excludes non-app surfaces: status/offline-fallback/design-system/
// symbol-gallery/validator-catalog/architecture/promo-poster (not first-run product pages).
const PAGES = process.env.WH_COLD_PAGES ? process.env.WH_COLD_PAGES.split(',')
  : ['index.html', 'hive.html', 'community.html', 'asset-hub.html', 'alert-hub.html',
  'dayplanner.html', 'shift-brain.html', 'assistant.html', 'voice-journal.html', 'achievements.html',
  'marketplace.html', 'marketplace-seller.html', 'project-manager.html', 'resume.html',
  'analytics-report.html', 'audit-log.html', 'integrations.html', 'report-sender.html',
    'plant-connections.html'];

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();

const residue = () => psql(`SELECT count(*) FROM auth.users WHERE email = '${EMAIL}'`);

if (residue() !== '0') {
  console.log('ABORT: a previous probe account still exists — refusing to measure on dirty state.');
  process.exit(2);
}

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
  const made = await auth.evaluate(async ({ email, pw, url, name }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { error: se } = await db.auth.signUp({
        email, password: pw, options: { data: { display_name: name, username: name } },
      });
      if (se && !/already/i.test(se.message || '')) return { ok: false, err: se.message };
      const { data, error } = await db.auth.signInWithPassword({ email, password: pw });
      if (error || !data?.session) return { ok: false, err: error?.message };
      // ★COLD MEANS "NO HIVE", NOT "NO IDENTITY", AND THE FIRST VERSION OF THIS PROBE GOT IT WRONG.
      // It also cleared wh_last_worker, and 14 of 19 pages promptly bounced to index.html - a
      // dramatic finding that was entirely an artifact. index.html:3196 sets wh_last_worker at
      // signup and :3650 re-seeds it from worker_profiles.display_name on session restore, and the
      // shared guard redirects on a missing WORKER NAME (utils.js:3546), not a missing hive. So the
      // probe had manufactured a state no real signup produces, and would have recorded a product
      // defect against its own setup. Seed the identity the way signup does; leave the hive empty,
      // which is the condition actually under test.
      let displayName = name;
      try {
        const { data: prof } = await db.from('worker_profiles').select('display_name')
          .eq('auth_uid', data.session.user.id).maybeSingle();
        if (prof?.display_name) displayName = prof.display_name;
      } catch (_) { /* the fallback name is fine */ }
      localStorage.setItem('wh_last_worker', displayName);
      ['wh_active_hive_id', 'wh_hive_id', 'wh_hive_name', 'wh_hive_role', 'wh_hive_list']
        .forEach((k) => localStorage.removeItem(k));
      return { ok: true, displayName };
    } catch (e) { return { ok: false, err: String(e) }; }
  }, { email: EMAIL, pw: PW, url: SB_URL, name: 'Probe Cold' });
  await auth.close();
  if (!made.ok) throw new Error('cold account not created: ' + (made.err || 'unknown'));
  console.log(`  cold account created (${EMAIL}) as "${made.displayName}" — identity seeded, NO hive`);

  for (const pg of PAGES) {
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).slice(0, 80)));
    await page.goto(`${BASE}/${pg}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(5000);
    const r = await page.evaluate(() => {
      // ★READ THE BODY, NOT <main>, AND READ ONLY WHAT IS VISIBLE. This probe originally locked onto
      // document.querySelector('main'), which broke on exactly the page it was meant to judge:
      // analytics-report puts its cold-state gate OUTSIDE <main> and sets <main> to display:none -
      // the correct shape, copied from shift-brain - and innerText on a display:none element still
      // returns its raw text. So the probe captured the HIDDEN generator, missed the VISIBLE gate,
      // and reported the page as ungated after it had just been gated. innerText on body respects
      // visibility, so a hidden region contributes nothing, which is what a reader sees.
      // THE WHOLE region, not a slice - the previous pass truncated above a teaching block.
      const txt = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
      return { chars: txt.length, text: txt, path: location.pathname };
    });
    await page.close();
    const bounced = !r.path.endsWith(pg);
    rows.push({ page: pg, chars: r.chars, bounced, errs: errs.length, text: r.text });
    console.log(`\n  --- ${pg}${bounced ? '  [BOUNCED -> ' + r.path + ']' : ''} `
      + `(${r.chars} chars, err=${errs.length})`);
    console.log('      ' + r.text.slice(0, 420));
  }
} catch (e) {
  fatal = String(e.message || e).slice(0, 170);
  console.log('probe error:', fatal);
} finally {
  try {
    psql(`DELETE FROM auth.users WHERE email = '${EMAIL}'`);
  } catch (e) { console.log('cleanup error:', String(e).slice(0, 100)); }
  await browser.close();
}

const clean = residue() === '0';
// ★THE THRESHOLD WAS 200 AND IT WAS MEASURING BREVITY, NOT EMPTINESS. It flagged four of the best
// cold states on the platform: hive.html at 134 chars ("Join or create a team... Create a Hive |
// Join with Code"), asset-hub at 188 ("Asset Hub needs a hive... Go to Hive"), shift-brain at 137,
// integrations at 193 ("Supervisor access only... ask your hive supervisor"). Those pages are SHORT
// BECAUSE THEY ARE FOCUSED - a refusal that names the precondition and the next tap is exactly what
// a first visit needs, and it does not take 200 characters to say. Only a region with essentially
// nothing in it is objectively wrong; whether prose TEACHES is a judgement this probe deliberately
// leaves to a reader of the captures, which is why every page's text is printed above.
const empty = rows.filter((r) => !r.bounced && r.chars < 40).map((r) => `${r.page}(${r.chars})`);
const broken = rows.filter((r) => r.errs > 0).map((r) => `${r.page}(${r.errs})`);
console.log(`\n  pages walked cold: ${rows.length} | near-empty regions: ${empty.length} `
  + `| pages throwing: ${broken.length} | probe account removed: ${clean}`);
if (empty.length) console.log(`  NEAR-EMPTY: ${empty.join(', ')}`);
if (broken.length) console.log(`  THROWING: ${broken.join(', ')}`);
const pass = !fatal && clean && rows.length === PAGES.length && empty.length === 0 && broken.length === 0;
console.log((pass ? 'PASS' : 'FAIL') + ` — cold pages: ${JSON.stringify({ walked: rows.length, empty: empty.length, broken: broken.length, clean, fatal })}`);
process.exit(pass ? 0 : 1);
