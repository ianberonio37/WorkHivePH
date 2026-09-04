/* prove_safety_isolation_visible.mjs — T15: the read path shows LOCK-OUT (2026-08-27).
 *
 * The point of searching fault history before opening a machine is to learn how it was worked on
 * last time, and "the last person locked this out / worked under a permit" is the most
 * consequential thing on the card. logbook CAPTURES loto_applied + permit_reference on the form,
 * STORES them on the row, and RESTORES them when an entry is edited - and never showed them to
 * anyone READING. 419 of 3,811 entries carry that data.
 *
 * THE ORACLE: count the badges the page renders and compare against what the DATABASE says should
 * be visible for the same worker's most recent page. Not "a badge exists somewhere" - the COUNT has
 * to match, because a badge that renders for the wrong rows is its own defect.
 *
 * ★THE SUBJECT MUST HAVE LOTO IN ITS VISIBLE PAGE. The first run of this probe used an account
 * whose recent 20 entries contained none, so it read 0 badges and 0 was CORRECT - a pass that
 * proved nothing. The account is chosen because its recent page contains some.
 *
 * Read-only. Usage: node tools/prove_safety_isolation_visible.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const ACCT = { email: 'wilfredomalabanan@auth.workhiveph.com', worker: 'Wilfredo Malabanan' };
const PAGE_SIZE = 20;

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8' }).trim();

const expected = Number(psql(
  `SELECT count(*) FILTER (WHERE loto_applied OR permit_reference IS NOT NULL) FROM (
     SELECT loto_applied, permit_reference FROM logbook
      WHERE worker_name = '${ACCT.worker}' ORDER BY date DESC, id DESC LIMIT ${PAGE_SIZE}) x;`));

const browser = await chromium.launch();
let cards = 0, badges = 0, sample = '';
try {
  const page = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && window.supabase.createClient), { timeout: 25000 });
  await page.evaluate(async ({ email, worker, hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email, password: 'test1234' });
    try {
      localStorage.setItem('wh_worker_name', worker); localStorage.setItem('wh_last_worker', worker);
      localStorage.setItem('wh_active_hive_id', hive.id); localStorage.setItem('wh_hive_id', hive.id);
      localStorage.setItem('wh_hive_name', hive.name);
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
  }, { email: ACCT.email, worker: ACCT.worker, hive: HIVE });

  await page.goto(`${SEEDER}/logbook.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.waitForSelector('#entries-list .entry-card', { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(2000);
  const r = await page.evaluate(() => {
    const c = [...document.querySelectorAll('#entries-list .entry-card')];
    const b = c.filter((x) => /LOTO/.test(x.innerText || ''));
    return { cards: c.length, badges: b.length, sample: (b[0]?.innerText || '').replace(/\s+/g, ' ').slice(0, 90) };
  });
  cards = r.cards; badges = r.badges; sample = r.sample;
} catch (e) {
  console.log('probe error:', String(e).slice(0, 180));
} finally {
  await browser.close();
}

console.log(`  cards rendered: ${cards}   LOTO badges: ${badges}   database expects: ${expected}`);
if (sample) console.log(`  sample: ${sample}`);
const problems = [];
if (!cards) problems.push('no entry cards rendered - nothing was measured');
if (!expected) problems.push('the chosen account has no LOTO entries on its visible page, so a 0 would prove nothing');
if (cards && expected && badges !== expected) problems.push(`badge count ${badges} != database ${expected}`);
console.log((problems.length ? 'FAIL' : 'PASS') + ' — safety isolation visible'
  + (problems.length ? ': ' + problems.join(' | ') : ''));
process.exit(problems.length ? 1 : 0);
