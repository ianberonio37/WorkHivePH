// prove_tile_canonical — the TILE == DB CANONICAL lens of the live-walk wave (2026-09-06).
//
// A number on a board is a claim about the database. This gate reads the number the page actually renders and
// compares it to the canonical layer (the v_*_truth views), one explicit pair at a time. Deliberately explicit:
// a heuristic that guessed which query backs which tile would be a second implementation of the product, and the
// disagreements it produced would be its own.
//
// ★EVERY PAIR BELOW WAS RECONCILED BY HAND FIRST, and three of my four initial "mismatches" were MY query:
//   · `stat-open` (10 open work orders) reads logbook.status = 'Open'. I asked v_logbook_truth.wo_state, which is
//     NULL on all 944 rows - an optional Phase-E field that logbook.html guards with `if (!wo_state) return ''`.
//   · `2 low` is low + critical, and the page states the out-of-stock one separately beside it.
//   · `3 of 27 parts at healthy stock` looked absurd next to 24 not-low parts - until stockStatus() says `ok` is
//     the MIDDLE band: not out, not critical (q <= m/2), not low (q <= m), and NOT surplus (q >= 3m). 21 are
//     surplus, so 3 is exact.
//   · the approval badge's 30 against the truth view's 27 is the one that found something: v_asset_truth ends
//     `WHERE status = 'approved'`, so the 3 PENDING asset_nodes are invisible to it. The badge is right because
//     asset-hub reads the raw table for its queue, the view's own COMMENT says "over approved asset_nodes", and
//     the drift auditor reports 0 drift reads - the contract is documented and nothing is steering that read
//     into the filtered view. It stays here as a pair so a future migration to the "canonical" source is caught.
//
//   node tools/prove_tile_canonical.mjs            # every pair
//   node tools/prove_tile_canonical.mjs --page hive.html
import { chromium } from 'playwright';
import { SEEDER, HIVE, signIn, VIS_JS, SETTLE_MS } from './prover_harness.mjs';
import { execSync } from 'node:child_process';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const psql = (sql) => { try { return execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql.replace(/"/g, '\\"')}"`, { encoding: 'utf8' }).trim(); } catch { return ''; } };
const H = `'${HIVE}'`;
const INV = `v_inventory_items_truth where hive_id=${H} and status='approved'`;
const STOCK = `case when qty_on_hand is null then 'unknown' when qty_on_hand <= 0 then 'out' when coalesce(min_qty,0) > 0 and qty_on_hand <= min_qty/2.0 then 'critical' when coalesce(min_qty,0) > 0 and qty_on_hand <= min_qty then 'low' when coalesce(min_qty,0) > 0 and qty_on_hand >= min_qty*3 then 'surplus' else 'ok' end`;

const PAIRS = [
  { page: 'hive.html', id: 'ss-pm-hero', what: 'assets with PM overdue',
    sql: `select count(distinct pm_asset_id) from v_pm_scope_items_truth where hive_id=${H} and is_overdue` },
  { page: 'hive.html', id: 'ss-stock-hero', what: 'parts low on stock (out-of-stock counted separately)',
    sql: `select count(*) from (select ${STOCK} s from ${INV}) t where s in ('low','critical')` },
  { page: 'hive.html', id: 'ss-jobs-hero', what: "the signed-in person's own open jobs",
    sql: `select count(*) from v_logbook_truth where hive_id=${H} and status='Open' and worker_name='Leandro Marquez'` },
  { page: 'hive.html', id: 'ss-rd-composite', what: 'readiness composite',
    sql: `select composite_score from v_hive_readiness_truth where hive_id=${H} order by snapshot_date desc limit 1` },
  { page: 'hive.html', id: 'stat-open', what: 'open work orders, hive-wide',
    sql: `select count(*) from v_logbook_truth where hive_id=${H} and status='Open'` },
  { page: 'hive.html', id: 'stat-members', what: 'active team members',
    sql: `select count(*) from hive_members where hive_id=${H} and status='active'` },
  { page: 'hive.html', id: 'adoption-risk-score', what: 'adoption risk',
    sql: `select risk_score from v_adoption_truth where hive_id=${H} order by snapshot_date desc limit 1` },
  { page: 'hive.html', id: 'pulse-jobs-today', what: 'jobs logged since midnight',
    sql: `select count(*) from v_logbook_truth where hive_id=${H} and created_at >= date_trunc('day', now())` },
  { page: 'hive.html', id: 'approval-badge', what: 'everything a supervisor owes a decision on (assets+parts+FMEA+strategies+briefings)',
    sql: `select (select count(*) from asset_nodes where hive_id=${H} and status='pending') + (select count(*) from inventory_items where hive_id=${H} and status='pending') + (select count(*) from rcm_fmea_modes where hive_id=${H} and approved_by is null) + (select count(*) from rcm_strategies where hive_id=${H} and approved_by is null) + (select count(*) from v_amc_truth where hive_id=${H} and status='pending')` },
  { page: 'inventory.html', id: 'stat-total', what: 'approved parts', sql: `select count(*) from ${INV}` },
  { page: 'inventory.html', id: 'stat-low', what: 'low + critical (the page says "low" for both)',
    sql: `select count(*) from (select ${STOCK} s from ${INV}) t where s in ('low','critical')` },
  { page: 'inventory.html', id: 'stat-out', what: 'out of stock',
    sql: `select count(*) from (select ${STOCK} s from ${INV}) t where s = 'out'` },
  { page: 'inventory.html', id: 'inv-out-hero', what: 'out-of-stock hero',
    sql: `select count(*) from (select ${STOCK} s from ${INV}) t where s = 'out'` },
  { page: 'inventory.html', id: 'inv-low-hero', what: 'low-stock hero',
    sql: `select count(*) from (select ${STOCK} s from ${INV}) t where s in ('low','critical')` },
  { page: 'inventory.html', id: 'inv-pending-hero', what: 'parts awaiting sign-off',
    sql: `select count(*) from inventory_items where hive_id=${H} and status='pending'` },
];

const READ = function read(args) {
  const ids = args[0];
  const vis = (0, eval)(args[1]);
  const out = {};
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) { out[id] = null; continue; }
    if (!vis(el)) { out[id] = '(hidden)'; continue; }
    out[id] = (el.innerText || el.textContent || '').replace(/[^0-9.]/g, '');
  }
  return out;
};

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
await signIn(ctx);
const pages = [...new Set(PAIRS.map((p) => p.page))].filter((f) => !ONLY || f === ONLY);
let bad = 0, n = 0;
for (const file of pages) {
  const mine = PAIRS.filter((p) => p.page === file);
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  const seen = await p.evaluate(READ, [mine.map((m) => m.id), VIS_JS]).catch(() => ({}));
  for (const m of mine) {
    n++;
    const glass = seen[m.id];
    const truth = psql(m.sql);
    const same = glass !== null && glass !== '(hidden)' && glass !== '' && String(Number(glass)) === String(Number(truth));
    if (!same) bad++;
    console.log(`  ${same ? 'ok  ' : 'DIFF'} ${file.padEnd(15)} #${m.id.padEnd(20)} glass=${String(glass).padStart(6)} canonical=${String(truth).padStart(6)}  ${m.what}`);
  }
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} tile-canonical - ${n - bad}/${n} rendered tiles equal the canonical layer`);
process.exit(bad ? 1 : 0);
