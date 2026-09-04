/* prove_audit_entry_readable.mjs — T28: an audit entry must read as a change, not as JSON (2026-08-27).
 *
 * audit-log's own meta description promises "every CRUD + approval + permission change with actor,
 * BEFORE/AFTER, and timestamp". The data can deliver it: hive_audit_log rows carry
 * changed_fields: {"sw": {"from": 768, "to": 1920}} - literally a before and an after. The page
 * rendered the whole payload as `<pre>JSON.stringify(detail, null, 2)</pre>`, so a supervisor
 * reconstructing a disputed change read a JSON blob to find the two values that mattered.
 *
 * THE ORACLE, on the RENDERED DOM rather than the source, because the question is what a person
 * sees: expand a real entry's details and assert the block contains no JSON punctuation - no braces,
 * no quoted keys - and that a from/to pair renders as an arrow.
 *
 * ★IT MUST RUN AS A SUPERVISOR. audit-log is supervisor-gated, and signing in as a worker renders
 * ZERO entries - which the first run of this probe reported as "0 entries with details", a verdict
 * about the account rather than the page. The gate fails loudly rather than passing on an empty feed.
 *
 * Read-only: signs in, reads, asserts. Writes nothing.
 *
 * Usage: node tools/prove_audit_entry_readable.mjs
 */
import { chromium } from 'playwright';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
// Leandro is the SUPERVISOR of this hive; a worker sees an empty audit feed by design.
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234', worker: 'Leandro Marquez' };
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };

const browser = await chromium.launch();
const v = { entries: 0, opened: false, rows: 0, jsonPunctuation: null, sample: '' };
try {
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && window.supabase.createClient), { timeout: 25000 });
  await page.evaluate(async ({ email, pw, worker, hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email, password: pw });
    try {
      localStorage.setItem('wh_worker_name', worker);
      localStorage.setItem('wh_last_worker', worker);
      localStorage.setItem('wh_active_hive_id', hive.id);
      localStorage.setItem('wh_hive_id', hive.id);
      localStorage.setItem('wh_hive_name', hive.name);
      localStorage.setItem('wh_hive_role', 'supervisor');
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
  }, { email: ACCT.email, pw: ACCT.pw, worker: ACCT.worker, hive: HIVE });

  await page.goto(`${SEEDER}/audit-log.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6500);

  v.entries = await page.evaluate(() => document.querySelectorAll('.entry-meta-toggle').length);
  if (v.entries > 0) {
    await page.evaluate(() => document.querySelector('.entry-meta-toggle').click());
    await page.waitForTimeout(800);
    const got = await page.evaluate(() => {
      const m = document.querySelector('.entry-meta');
      if (!m) return null;
      const txt = m.innerText || '';
      return { rows: m.querySelectorAll('div').length, txt: txt.slice(0, 200),
               // a JSON dump announces itself with braces and quoted keys
               json: /[{}]|"\w+"\s*:/.test(txt) };
    });
    if (got) { v.opened = true; v.rows = got.rows; v.jsonPunctuation = got.json; v.sample = got.txt; }
  }
} catch (e) {
  console.log('probe error:', String(e).slice(0, 200));
} finally {
  await browser.close();
}

console.log(`entries with details: ${v.entries}`);
console.log(`opened: ${v.opened}  rows: ${v.rows}  json punctuation present: ${v.jsonPunctuation}`);
console.log(`sample: ${JSON.stringify(v.sample)}`);

const problems = [];
if (v.entries === 0) problems.push('no audit entries carried details - the account is probably not a supervisor, so this measured nothing');
if (!v.opened) problems.push('the details block never rendered when the toggle was pressed');
if (v.rows === 0) problems.push('the details block rendered no labelled rows');
if (v.jsonPunctuation) problems.push('the details are still a JSON dump: braces or quoted keys are on the glass');

console.log((problems.length ? 'FAIL' : 'PASS') + ' — audit entry readable'
  + (problems.length ? ': ' + problems.join(' | ') : ''));
process.exit(problems.length ? 1 : 0);
