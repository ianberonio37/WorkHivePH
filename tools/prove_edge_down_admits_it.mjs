/* prove_edge_down_admits_it.mjs — T198: a dead edge fn must not become a confident answer.
 *
 * Edge functions fail independently of the database - a cold start times out, one function is
 * mid-deploy, a region hiccups. The page keeps working, which is the point of the client fallback.
 * The danger is the fallback filling the gap with a POSITIVE-LOOKING ZERO.
 *
 * ★MEASURED, AND IT WAS REAL. project-manager's clientRollup returned
 * `critical_path: { item_ids: [], total_days: 0, slack_per_item: {} }` when project-progress was
 * unreachable. renderCpm() has a PJ8 guard written for exactly this - `if (!cp)` prints "The
 * critical path could not be computed right now" - but an EMPTY OBJECT IS TRUTHY, so the guard
 * never fired on the path it was written for. With the edge fn down, a shutdown project whose real
 * schedule is "12d, 7 of 7 items on the critical path" rendered as:
 *
 *     CRITICAL PATH 0d · 0 of 7 items on critical path   [full Gantt beneath]
 *
 * Not a blank, not an error - a confident inversion, on the screen a supervisor uses to plan a
 * plant outage. Fixed by returning `critical_path: null` so the existing message speaks; every
 * consumer already used optional chaining. The EVM half of that same fallback had received its
 * marker (evm_reason: 'unavailable') and the CPM half had been left behind.
 *
 * THE ASSERTION: with project-progress forced to 503, the CPM pane SAYS it could not compute -
 * and with the function up, it still renders a real schedule. Both directions, because a gate that
 * only checks the failure case would pass on a pane that is permanently broken.
 *
 * Usage: node tools/prove_edge_down_admits_it.mjs
 */
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const SB_URL = process.env.WH_SUPABASE_URL || 'http://127.0.0.1:54321';
const ACCT = { email: 'leandromarquez@auth.workhiveph.com', pw: 'test1234',
               worker: 'Leandro Marquez', hiveName: 'Baguio Textile Mills' };

// a shutdown/capex project is the only kind with a Schedule+Risk tab; resolve one rather than
// hardcoding an id that a reseed would invalidate
function pickProject() {
  const out = execFileSync('docker',
    ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-d', 'postgres', '-t', '-A', '-c',
      "SELECT id FROM projects WHERE project_type IN ('shutdown','capex') "
      + "AND id IN (SELECT project_id FROM project_items) LIMIT 1;"],
    { encoding: 'utf8' }).trim().split('\n')[0];
  return out || null;
}

const pid = pickProject();
if (!pid) {
  console.log('SKIP — no shutdown/capex project with scope items in this fixture');
  process.exit(0);
}

const browser = await chromium.launch();
const v = { project: pid };
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  const auth = await ctx.newPage();
  await auth.goto(`${BASE}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await auth.waitForFunction(
    () => !!(window.supabase && window.supabase.createClient) && !!window.SUPABASE_KEY,
    { timeout: 20000 }).catch(() => {});
  const ok = await auth.evaluate(async ({ acct, url }) => {
    try {
      const db = window._whSupabaseClient || window.getDb(url, window.SUPABASE_KEY);
      const { data, error } = await db.auth.signInWithPassword({ email: acct.email, password: acct.pw });
      const uid = data?.session?.user?.id;
      const { data: m } = uid ? await db.from('hive_members').select('hive_id')
        .eq('auth_uid', uid).eq('status', 'active').limit(1).maybeSingle() : { data: null };
      if (m?.hive_id) {
        localStorage.setItem('wh_active_hive_id', m.hive_id);
        localStorage.setItem('wh_hive_id', m.hive_id);
      }
      localStorage.setItem('wh_last_worker', acct.worker);
      localStorage.setItem('wh_hive_name', acct.hiveName);
      localStorage.setItem('wh_hive_role', 'supervisor');
      return !error && !!data?.session;
    } catch (e) { return false; }
  }, { acct: ACCT, url: SB_URL });
  await auth.close();
  if (!ok) throw new Error('sign-in failed');

  const read = async (edgeDown) => {
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
    if (edgeDown) {
      await page.route('**/functions/v1/project-progress*', (r) => r.fulfill({
        status: 503, contentType: 'application/json',
        body: JSON.stringify({ error: 'cold start failed' }),
      }));
    }
    await page.goto(`${BASE}/project-manager.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(7000);
    const out = await page.evaluate(async (p) => {
      if (typeof openDetail !== 'function') return { noFn: true };
      await openDetail(p);
      await new Promise((r) => setTimeout(r, 4500));
      const tab = document.querySelector('#detail-tabs button[data-pane=cpm]');
      if (!tab) return { noTab: true };
      tab.click();
      await new Promise((r) => setTimeout(r, 2000));
      const t = (document.getElementById('pane-cpm').innerText || '').replace(/\s+/g, ' ').trim();
      return {
        text: t.slice(0, 120),
        admits: /could not be computed/i.test(t),
        claimsSchedule: /critical path\s+\d+d/i.test(t),
      };
    }, pid);
    await page.close();
    return { ...out, errs: errs.length };
  };

  v.up = await read(false);
  v.down = await read(true);
  console.log(`  edge UP   -> ${v.up.text}`);
  console.log(`  edge DOWN -> ${v.down.text}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 160);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const pass = !v.error && v.up && v.down && !v.up.noTab && !v.down.noTab
  && v.up.claimsSchedule && !v.up.admits            // healthy: a real schedule
  && v.down.admits && !v.down.claimsSchedule        // outage: says so, claims nothing
  && v.up.errs === 0 && v.down.errs === 0;
if (!pass && !v.error) {
  console.log('  With the schedule engine unreachable the pane must SAY so. A "0d, 0 of N items on');
  console.log('  the critical path" is not an empty state - it is a confident inversion of the truth,');
  console.log('  on the screen used to plan a plant outage.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — edge down admits it: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
