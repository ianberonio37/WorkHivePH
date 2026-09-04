/* prove_tile_count_agreement.mjs — T19's tile→list count-agreement oracle (2026-08-26).
 *
 * THE ORACLE: the number a person taps is the number they land on. An ops-home tile reading
 * "6 PM Overdue" is a CLAIM about a filtered list somewhere else; if the landing page shows a
 * different figure (or loses the filter), morning triage becomes a scavenger hunt. Pagination
 * makes row-counting a lie, so the oracle compares STATED totals: the tile's number against the
 * landing page's own rendered total for the same subject, with the deep-link filter applied.
 *
 * Cases (slice 1 — the two handoffs whose landing filter + stated total both exist):
 *   pm-overdue: index tile N -> pm-scheduler.html?filter=overdue -> overdue chip ACTIVE and
 *               #pm-overdue-sub states "N of M assets past due" with the same N.
 *   open-jobs:  index tile N -> logbook.html?view=team&status=Open -> the HIVE window + filter
 *               both carried, and the team result rows count N (cap-guarded at 20/batch). The
 *               first run caught tile=9 landing on the mine-pill's 2 - two true numbers in
 *               different windows, fixed by carrying the window in the href.
 * The low-stock tile is RECORDED, not covered: its count spans three stock bands
 * (out+critical+low) that inventory's one-value filter select cannot express — the landing
 * handoff for it is a named T19 follow-up, not a silently-skipped case.
 *
 * Usage: node tools/prove_tile_count_agreement.mjs
 */
import { chromium } from 'playwright';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const ACCT = { email: 'bryangarcia@auth.workhiveph.com', pw: 'test1234', worker: 'Bryan Garcia' };

async function signInDirect(page) {
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  // getDb EXISTS from utils.js load but THROWS until the supabase lib arrives — wait for createClient.
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  return page.evaluate(async ({ email, password, worker, hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    const { error } = await db.auth.signInWithPassword({ email, password });
    if (error) return { ok: false, err: error.message };
    try {
      localStorage.setItem('wh_worker_name', worker);
      localStorage.setItem('wh_last_worker', worker);
      localStorage.setItem('wh_active_hive_id', hive.id);
      localStorage.setItem('wh_hive_id', hive.id);
      localStorage.setItem('wh_hive_name', hive.name);
      localStorage.setItem('wh_hive_role', 'worker');
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
    return { ok: true };
  }, { email: ACCT.email, password: ACCT.pw, worker: ACCT.worker, hive: HIVE });
}

async function readTile(page, kpi) {
  await page.goto(`${SEEDER}/index.html`, { waitUntil: 'domcontentloaded' });
  const t0 = Date.now();
  while (Date.now() - t0 < 30000) {
    const r = await page.evaluate((k) => {
      const tile = document.querySelector(`[data-kpi="${k}"]`);
      if (!tile) return null;
      const m = (tile.innerText || '').match(/\d+/);
      return m ? { n: Number(m[0]), href: tile.getAttribute('href') } : null;
    }, kpi);
    if (r) return r;
    await page.waitForTimeout(600);
  }
  throw new Error(`tile ${kpi} never rendered a number`);
}

const browser = await chromium.launch();
const results = [];
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await ctx.newPage();
const s = await signInDirect(page);
if (!s.ok) { console.log('FAIL — sign-in: ' + s.err); process.exit(1); }

// ── case 1: pm-overdue ──
{
  let v = { id: 'pm-overdue', tile: null, landed: null, filterOn: false, agree: false, note: '' };
  try {
    const t = await readTile(page, 'pm-overdue');
    v.tile = t.n;
    if (!/filter=overdue/.test(t.href || '')) throw new Error(`tile href lost the filter: ${t.href}`);
    await page.goto(`${SEEDER}/${t.href}`, { waitUntil: 'domcontentloaded' });
    const t0 = Date.now();
    while (Date.now() - t0 < 30000) {
      const st = await page.evaluate(() => ({
        chip: !!document.querySelector('.filter-chip.active[data-filter="overdue"]'),
        sub: (document.getElementById('pm-overdue-sub') || {}).textContent || '',
      }));
      v.filterOn = st.chip;
      const m = st.sub.match(/(\d+) of \d+ assets past due/) || (/^No overdue PMs/.test(st.sub) ? [null, '0'] : null);
      if (m && st.chip) { v.landed = Number(m[1]); break; }
      await page.waitForTimeout(600);
    }
    v.agree = v.landed !== null && v.landed === v.tile;
    v.note = `tile=${v.tile} landed=${v.landed} chipActive=${v.filterOn}`;
  } catch (e) { v.note = String(e).slice(0, 140); }
  results.push(v);
  console.log(`${v.agree ? 'ok' : 'RED'}  pm-overdue: ${v.note}`);
}

// ── case 2: open-jobs ──
{
  let v = { id: 'open-jobs', tile: null, landed: null, filterOn: false, agree: false, note: '' };
  try {
    const t = await readTile(page, 'open-jobs');
    v.tile = t.n;
    // The tile counts the HIVE window, so the href must carry BOTH the window and the filter -
    // the first run of this oracle caught tile=9 landing on the mine-view pill's 2 (both true,
    // different windows: the two-windows-one-metric class as a tap).
    if (!/view=team/.test(t.href || '') || !/status=Open/.test(t.href || ''))
      throw new Error(`tile href lost window/filter: ${t.href}`);
    await page.goto(`${SEEDER}/${t.href}`, { waitUntil: 'domcontentloaded' });
    const t0 = Date.now();
    while (Date.now() - t0 < 30000) {
      const st = await page.evaluate(() => ({
        filterVal: (document.getElementById('filter-status') || {}).value || '',
        rows: document.querySelectorAll('#entries-list .entry-card').length,
        searching: /Searching team entries/.test((document.getElementById('entries-list') || {}).innerText || ''),
      }));
      v.filterOn = st.filterVal === 'Open';
      if (v.filterOn && !st.searching && st.rows > 0) { v.landed = st.rows; break; }
      await page.waitForTimeout(600);
    }
    // Team results page at 20/batch: row-count agreement is only assertable under the cap.
    if (v.tile > 20 && v.landed === 20) { v.agree = true; v.note = `tile=${v.tile} > page cap 20, first batch full (cap-limited check)`; }
    else { v.agree = v.landed !== null && v.landed === v.tile; v.note = `tile=${v.tile} teamRows=${v.landed} filterApplied=${v.filterOn}`; }
  } catch (e) { v.note = String(e).slice(0, 140); }
  results.push(v);
  console.log(`${v.agree ? 'ok' : 'RED'}  open-jobs: ${v.note}`);
}

await browser.close();
const bad = results.filter(r => !r.agree);
console.log((bad.length ? 'FAIL' : 'PASS') + ` — tile count agreement: ${results.length - bad.length}/${results.length} handoffs carry their number (low-stock recorded as the multi-band follow-up).`);
process.exit(bad.length ? 1 : 0);
