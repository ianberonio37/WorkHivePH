/* prove_persona_follows_the_account.mjs — T85: the companion choice must cross devices.
 *
 * The persona lives in two places: localStorage (what every renderer and prompt-builder reads)
 * and worker_profiles.preferred_persona (the account-level choice). Only index.html and
 * voice-journal.html bridged them. assistant.html - a page reachable directly, from the nav hub,
 * a deep link, or a fresh browser - read localStorage alone, so a worker who chose Hezekiah on
 * their phone was answered by ZANIAH on a PC while their account said Hezekiah.
 *
 * ★THE FAILURE IS SILENT BECAUSE THE WRONG ANSWER IS THE DEFAULT. Nothing errors, nothing looks
 * broken; the companion is simply not the one they picked. That is why it needs a live probe
 * rather than a reading of the code: the only way to see it is to arrive with an empty
 * localStorage and ask who answers.
 *
 * TWO DIRECTIONS, because a one-way check would pass on a page that always overwrites:
 *   1. FOLLOWS   — account says hezekiah, localStorage empty  -> resolves hezekiah
 *   2. NO CLOBBER — account read yields nothing usable, localStorage says hezekiah
 *                   -> STAYS hezekiah. The replaced inline copy failed exactly here: it
 *                   destructured { data: profile } without checking the error, so a transient
 *                   blip fell through to 'zaniah' and WROTE it, resetting the worker's choice
 *                   permanently because one read failed. An unreadable preference is not
 *                   evidence of a preference.
 *
 * Restores the account's original persona value on the way out, pass or fail.
 *
 * Usage: node tools/prove_persona_follows_the_account.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234' };

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();

const UID_SQL = `SELECT wp.auth_uid FROM worker_profiles wp JOIN auth.users u ON u.id=wp.auth_uid
                 WHERE u.email='${ACCT.email}' LIMIT 1;`;
const uid = psql(UID_SQL).split('\n')[0];
if (!uid) { console.log('SKIP — no worker_profiles row for the test account'); process.exit(0); }
const original = psql(`SELECT preferred_persona FROM worker_profiles WHERE auth_uid='${uid}';`).split('\n')[0];

const v = { original };
const browser = await chromium.launch();
try {
  // the account now prefers hezekiah — the opposite of the default, so a pass cannot be luck
  psql(`UPDATE worker_profiles SET preferred_persona='hezekiah' WHERE auth_uid='${uid}';`);

  const open = async (seedLocal, breakRead) => {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
    if (breakRead) {
      // the profile read fails the way a real one does - a blip, not a missing row. The column
      // is NOT NULL, so an unusable preference can ONLY arrive as an error, which is precisely
      // the case the replaced code mishandled.
      await page.route('**/rest/v1/worker_profiles*', (r) => r.fulfill({
        status: 500, contentType: 'application/json', body: JSON.stringify({ message: 'read failed' }),
      }));
    }
    await page.goto(`${BASE}/assistant.html`, { waitUntil: 'domcontentloaded' });
    await page.evaluate(async ({ acct, url, seed }) => {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
      try { localStorage.removeItem('wh_voice_journal_persona'); } catch (_) {}
      if (seed) { try { localStorage.setItem('wh_voice_journal_persona', seed); } catch (_) {} }
    }, { acct: ACCT, url: SB_URL, seed: seedLocal });
    // reload so the signed-in session is present during the page's own bootstrap
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    const out = await page.evaluate(() => ({
      resolved: (typeof window.getPersonaKey === 'function') ? window.getPersonaKey() : null,
      stored: (() => { try { return localStorage.getItem('wh_voice_journal_persona'); } catch (_) { return null; } })(),
      hasHelper: typeof window.hydratePersonaFromCloud === 'function',
    }));
    await ctx.close();
    return { ...out, errs: errs.length };
  };

  v.follows = await open(null, false);            // empty localStorage -> must take the account's hezekiah

  // the profile read now fails; a local choice must SURVIVE it
  psql(`UPDATE worker_profiles SET preferred_persona='zaniah' WHERE auth_uid='${uid}';`);
  v.noClobber = await open('hezekiah', true);    // read errors -> must keep hezekiah, not reset

  console.log(`  account=hezekiah, localStorage empty  -> ${v.follows.resolved}`);
  console.log(`  profile read 500, localStorage=hezekiah -> ${v.noClobber.resolved}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 170);
  console.log('probe error:', v.error);
} finally {
  try { psql(`UPDATE worker_profiles SET preferred_persona='${original}' WHERE auth_uid='${uid}';`); } catch (_) {}
  await browser.close();
}

const pass = !v.error
  && v.follows && v.follows.hasHelper
  && v.follows.resolved === 'hezekiah'     // the account's choice crossed to a fresh device
  && v.noClobber && v.noClobber.resolved === 'hezekiah'  // an unreadable preference changed nothing
  && v.follows.errs === 0 && v.noClobber.errs === 0;

if (!pass && !v.error) {
  console.log('  A companion the worker did not pick is not a wrong default - it is their choice');
  console.log('  being ignored, and it is silent, because the wrong answer IS the default.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — persona follows the account: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
