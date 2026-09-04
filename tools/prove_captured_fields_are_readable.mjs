/* prove_captured_fields_are_readable.mjs — T15: what the form captures, a reader can read (2026-08-27).
 *
 * Generalising T15's LOTO finding produced four more columns in the same shape: selected by the
 * loader, mapped onto the entry, restored into the EDIT FORM, and rendered to a reader NOWHERE.
 * Two of them are T15's own scenario - someone searching fault history before opening a machine:
 *
 *   readings_json        1767 of 3811 rows   what the last person measured
 *   failure_consequence  1075 of 3811 rows   Safety risk | Stopped production | Running reduced | Hidden
 *
 * ★AND THE FIRST FIX WAS HALF A FIX. The LOTO badge went on the entry CARD only, so the safety flag
 * VANISHED on drill-down - the detail modal is the surface a person actually reads before working
 * on a machine. This prover therefore checks BOTH read surfaces, because "it renders somewhere" was
 * exactly the belief that let the modal stay blind.
 *
 * THE ORACLE is the database, per surface:
 *   - the CARD list: consequence-badge count === rows on the visible page carrying one;
 *   - the DETAIL MODAL: open an entry the DB says has readings + a consequence, and require both
 *     to appear, with a UNIT on the readings (a bare "97" is the naked-number defect).
 * A count is compared, never mere presence: a badge that renders for the wrong rows is its own bug,
 * and the LOTO run that read 0-and-was-correct proved presence checks can pass while blind.
 *
 * Read-only: signs in, reads, opens a modal. Writes nothing.
 * Usage: node tools/prove_captured_fields_are_readable.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const ACCT = { email: 'bryangarcia@auth.workhiveph.com', worker: 'Bryan Garcia' };
const PAGE_SIZE = 20;

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8', env: { ...process.env, MSYS_NO_PATHCONV: '1' } }).trim();

// what the visible page SHOULD show, straight from the table
const recentCte = `with recent as (select * from logbook where hive_id='${HIVE.id}'`
  + ` and worker_name='${ACCT.worker}' order by date desc limit ${PAGE_SIZE})`;
const expectConsequence = Number(psql(
  `${recentCte} select count(*) from recent where failure_consequence is not null;`));
// a subject for the modal: newest visible entry carrying BOTH
const subject = psql(`${recentCte} select id || '|' || failure_consequence`
  + ` from recent where readings_json is not null and failure_consequence is not null limit 1;`);

const problems = [];
let measured = { badges: null, modal: null };

if (!subject) {
  problems.push(`no entry on ${ACCT.worker}'s visible page carries both readings and a consequence `
    + `- the run would prove nothing (the LOTO lesson: 0 can be the correct answer)`);
}

const browser = await chromium.launch();
try {
  const page = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && window.supabase.createClient), { timeout: 25000 });
  await page.evaluate(async ({ email, worker, hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email, password: 'test1234' });
    localStorage.setItem('wh_active_hive_id', hive.id);
    localStorage.setItem('wh_active_hive_name', hive.name);
    localStorage.setItem('WORKER_NAME', worker);
  }, { email: ACCT.email, worker: ACCT.worker, hive: HIVE });

  await page.goto(`${SEEDER}/logbook.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  await page.waitForSelector('#entries-list .entry-card', { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(2000);

  // ── surface 1: the card list ──────────────────────────────────────────────────────────────────
  measured.badges = await page.evaluate(() => {
    const cards = [...document.querySelectorAll('#entries-list .entry-card')];
    const re = /Safety risk|Stopped production|Running reduced|Hidden/;
    return { cards: cards.length, withBadge: cards.filter((c) => re.test(c.innerText || '')).length };
  });

  // ── surface 2: the detail modal ───────────────────────────────────────────────────────────────
  if (subject) {
    const [id, consequence] = subject.split('|');
    measured.modal = await page.evaluate(async (entryId) => {
      if (typeof openModal !== 'function') return { err: 'openModal is not reachable' };
      await openModal(entryId);
      await new Promise((r) => setTimeout(r, 700));
      const el = document.getElementById('modal-content');
      const txt = el ? (el.innerText || '') : '';
      return {
        text: txt,
        hasReadingsHeading: /Readings taken/i.test(txt),
        // a value with a unit beside it - the naked-number bar
        hasUnitedValue: /\d(\.\d+)?\s*(°C|bar|mm\/s|A|V|mA|Hz|rpm|kW|psi|mm|%)\b/.test(txt),
      };
    }, id);

    if (measured.modal.err) problems.push(measured.modal.err);
    else {
      if (!measured.modal.hasReadingsHeading) problems.push('the detail modal shows no "Readings taken" section for an entry the database says has readings');
      if (!measured.modal.hasUnitedValue) problems.push('the readings render without units - a bare number is the naked-number defect');
      if (measured.modal.text.indexOf(consequence) < 0) problems.push(`the detail modal never shows the failure consequence "${consequence}" the row carries`);
    }
  }
} catch (e) {
  problems.push(`probe error: ${String(e).slice(0, 200)}`);
} finally {
  await browser.close();
}

if (measured.badges) {
  const { cards, withBadge } = measured.badges;
  console.log(`  cards rendered: ${cards}  ·  consequence badges: ${withBadge}  ·  database says: ${expectConsequence}`);
  if (!cards) problems.push('no entry cards rendered - nothing was measured');
  else if (withBadge !== expectConsequence) {
    problems.push(`the card list shows ${withBadge} consequence badges where the database says ${expectConsequence}`);
  }
}
if (measured.modal && !measured.modal.err) {
  console.log(`  detail modal: readings=${measured.modal.hasReadingsHeading} units=${measured.modal.hasUnitedValue}`);
}

console.log(`\n${problems.length ? 'FAIL' : 'PASS'} — what the form captures, a reader can read`
  + (problems.length ? '' : ' (card + detail modal both speak)'));
for (const p of problems) console.log(`    ${p}`);
process.exit(problems.length ? 1 : 0);
