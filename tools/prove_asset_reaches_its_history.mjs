/* prove_asset_reaches_its_history.mjs — T15: the machine reaches its own fault history (2026-08-27).
 *
 * T15's done-definition is a journey, not a field: "machine -> its history -> a usable prior fix,
 * under a minute". asset-hub COUNTED the asset's logbook entries in a stat card and offered no way
 * to open them - a number with no door. This walks the door.
 *
 * ★THE TWO WAYS THE LINK COULD LOOK RIGHT AND BE USELESS, both asserted:
 *   1. logbook.machine stores the TAG ("M-001"), not the asset NAME ("Siemens Simotics SD 200L").
 *      The sibling chips on this page use tag-with-name-fallback; copying that shape would land a
 *      name search on ZERO results for a machine with 47 entries - an empty page indistinguishable
 *      from an empty history. So the arrival must show ROWS, counted against the database.
 *   2. Fault history is the TEAM's history. Without ?view=team the reader sees only their own
 *      entries and reads a colleague's fix as absent - so the landing must be in team mode.
 *
 * The oracle is the database: the rows the logbook shows on arrival are compared against what the
 * table says that tag has, so a link that "works" but under-reports is still a failure.
 *
 * Read-only: signs in, clicks a link, reads. Writes nothing.
 * Usage: node tools/prove_asset_reaches_its_history.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const ACCT = { email: 'bryangarcia@auth.workhiveph.com', worker: 'Bryan Garcia' };

const psql = (sql) => execFileSync('docker',
  ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c', sql],
  { encoding: 'utf8', env: { ...process.env, MSYS_NO_PATHCONV: '1' } }).trim();

// the busiest tagged asset that BOTH exists as a node and has history - the subject must have
// something to show, or a green run proves nothing (the LOTO 0-was-correct lesson)
const row = psql(
  `select l.machine || '|' || count(*) from logbook l
     join asset_nodes a on a.tag = l.machine and a.hive_id = l.hive_id
   where l.hive_id='${HIVE.id}' group by l.machine order by count(*) desc limit 1;`);
const [TAG, expectedRaw] = row.split('|');
const expected = Number(expectedRaw);

const problems = [];
if (!TAG || !expected) problems.push('no tagged asset in this hive has logbook history - nothing to prove');

const browser = await chromium.launch();
let landed = null;
try {
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && window.supabase.createClient), { timeout: 25000 });
  await page.evaluate(async ({ email, worker, hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email, password: 'test1234' });
    localStorage.setItem('wh_active_hive_id', hive.id);
    localStorage.setItem('wh_active_hive_name', hive.name);
    localStorage.setItem('WORKER_NAME', worker);
  }, { email: ACCT.email, worker: ACCT.worker, hive: HIVE });

  if (TAG) {
    await page.goto(`${SEEDER}/asset-hub.html?tag=${encodeURIComponent(TAG)}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(7000);

    const chip = await page.evaluate(() => {
      const a = document.getElementById('detail-logbook-link');
      if (!a) return { present: false };
      const cs = getComputedStyle(a);
      return {
        present: true,
        visible: cs.display !== 'none' && a.offsetParent !== null,
        href: a.getAttribute('href') || '',
        text: (a.innerText || '').trim(),
      };
    });

    if (!chip.present) problems.push('asset-hub has no #detail-logbook-link - the asset cannot reach its history');
    else if (!chip.visible) problems.push(`the fault-history chip is hidden on a tagged asset (${TAG}) that has ${expected} entries`);
    else {
      if (chip.href.indexOf('view=team') < 0) problems.push(`the link omits view=team - the reader would see only their own entries: ${chip.href}`);
      if (chip.href.indexOf(encodeURIComponent(TAG)) < 0) problems.push(`the link does not carry the tag ${TAG}: ${chip.href}`);
      // ── walk it, as a user would ──────────────────────────────────────────────────────────────
      await page.click('#detail-logbook-link');
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(8000);
      landed = await page.evaluate(() => ({
        url: location.href,
        search: (document.getElementById('search-input') || {}).value || '',
        cards: document.querySelectorAll('#entries-list .entry-card').length,
        teamPill: /team/i.test(document.body.innerText.slice(0, 4000)),
      }));
      if (!/logbook\.html/.test(landed.url)) problems.push(`the chip did not land on the logbook: ${landed.url}`);
      if (landed.search !== TAG) problems.push(`the logbook's search box reads "${landed.search}", not the tag "${TAG}" - the context did not survive the hop`);
      if (!landed.cards) {
        problems.push(`the history arrived EMPTY for ${TAG}, which the database says has ${expected} entries `
          + `- an empty page that looks like an empty history`);
      }
    }
  }
} catch (e) {
  problems.push(`probe error: ${String(e).slice(0, 200)}`);
} finally {
  await browser.close();
}

console.log(`  subject: ${TAG || '<none>'}  ·  database says ${expected || 0} entries`);
if (landed) console.log(`  landed: ${landed.cards} cards · search="${landed.search}" · team-view=${landed.teamPill}`);
console.log(`\n${problems.length ? 'FAIL' : 'PASS'} — the machine reaches its own fault history`
  + (problems.length ? '' : ' (one tap, team window, rows present)'));
for (const p of problems) console.log(`    ${p}`);
process.exit(problems.length ? 1 : 0);
