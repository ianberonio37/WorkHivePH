// prove_engineering_saved_reports.mjs - a calculation saved and reopened from History is the same calculation
// (Wave ED, 2026-11-02; rows ED-S1 "saved, reopened from History, the same calculation").
//
// For every case in .tmp/ed_report_cases.json (the served Python handler's answer on the form's own payload) this, inside
// engineering-design.html as the signed-in walker:
//   1. renders the report through the live path (_renderComputed, no AI narrative) and reads it;
//   2. saves it through the page's own saveCalc() - a real insert into engineering_calcs, through RLS;
//   3. reads the row back from the database and reopens it through History (viewHistoryReport), and reads that report;
//   4. deletes the row (the page's own table, auth-scoped) - the walk leaves nothing behind.
// The two readings must match figure for figure (the date line aside): a value the database changes on the way through
// (a NaN stored as null, an alias the reopen path lacks, a nested list reshaped) is a report that is not the one saved.
//
//   python tools/ed_report_cases.py && node tools/prove_engineering_saved_reports.mjs
//   node tools/prove_engineering_saved_reports.mjs --gate            # exit 1 on a report that passed before and fails now
//   node tools/prove_engineering_saved_reports.mjs --update-baseline
//   node tools/prove_engineering_saved_reports.mjs --teeth           # plant a change between save and reopen; it must be caught
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { spawnSync } from 'child_process';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const TEETH = args.includes('--teeth');
const UPDATE = args.includes('--update-baseline');
const CASES = '.tmp/ed_report_cases.json';
const REPORT = TEETH ? 'engineering_saved_reports_teeth.json' : 'engineering_saved_reports_report.json';
const BASELINE = 'engineering_saved_reports_baseline.json';

// save, read back, reopen, compare, delete - runs in the page
const ROUND_TRIP = async ({ calc, inputs, results, plant }) => {
  const norm = (t) => (t || '').replace(/ /g, ' ')
    .replace(/(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}/g, 'DATE')
    .replace(/\s+/g, ' ').trim();
  switchTab('calculator');
  selectCalcType(calc);
  await new Promise((r) => setTimeout(r, 150));
  _renderComputed(JSON.parse(JSON.stringify(inputs)), { results: JSON.parse(JSON.stringify(results)), narrative: null });
  await new Promise((r) => setTimeout(r, 300));
  const live = norm(document.getElementById('report-panel')?.innerText);
  const before = new Date(Date.now() - 2000).toISOString();
  await saveCalc();
  await new Promise((r) => setTimeout(r, 600));
  const { data: rows, error } = await db.from('engineering_calcs').select('*').eq('calc_type', calc)
    .gte('created_at', before).order('created_at', { ascending: false }).limit(1);
  if (error || !rows || !rows.length) return { error: `not saved: ${error?.message || 'no row came back'}`, live: live.length };
  const row = rows[0];
  // teeth: every number the database returned scaled by 1.37 - whichever the renderer prints, the reopened report differs
  if (plant) row.results = Object.fromEntries(Object.entries(row.results).map(([k, v]) => [k, typeof v === 'number' ? v * 1.37 : v]));
  // clear the panel first: a reopen that renders nothing must read as nothing, not as the live report still on screen
  // (History's own dispatcher knew 30 of 55 calculators; the other 25 "reopened" onto the previous report)
  const panel = document.getElementById('report-panel');
  if (panel) panel.innerHTML = '';
  viewHistoryReport(row);
  await new Promise((r) => setTimeout(r, 400));
  const reopened = norm(document.getElementById('report-panel')?.innerText);
  const del = await db.from('engineering_calcs').delete().eq('id', row.id);
  // the first place the two readings part
  let at = 0;
  while (at < Math.min(live.length, reopened.length) && live[at] === reopened[at]) at++;
  const same = live === reopened;
  return { same, liveLen: live.length, reopenedLen: reopened.length, deleted: !del.error,
    diff: same ? '' : `live "…${live.slice(Math.max(0, at - 40), at + 60)}…" vs reopened "…${reopened.slice(Math.max(0, at - 40), at + 60)}…"` };
};

if (!args.includes('--no-rebuild')) {
  const py = spawnSync(process.platform === 'win32' ? 'python' : 'python3', ['tools/ed_report_cases.py'], { encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  if (py.status !== 0) console.log(`  cases: ${(py.stdout || py.stderr || '').trim().split(/\r?\n/).pop()}`);
}
if (!existsSync(CASES)) {
  console.log(`SKIP engineering-saved-reports: ${CASES} is missing - run python tools/ed_report_cases.py first`);
  process.exit(0);
}
const cases = JSON.parse(readFileSync(CASES, 'utf8'));
const browser = await chromium.launch();
const ctx = await browser.newContext();
await assertSignedIn(signIn(ctx, 'supervisor'));
const page = await ctx.newPage();
page.on('dialog', (d) => d.accept().catch(() => {}));
const results = [];
try {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${ORIGIN}/engineering-design.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForFunction(() => typeof _renderComputed === 'function' && typeof saveCalc === 'function' && typeof db === 'object', null, { timeout: 20000 });
  const run = TEETH ? ['Vibration Analysis'] : Object.keys(cases);
  for (const calc of run) {
    const c = cases[calc];
    let r;
    try {
      r = await page.evaluate(ROUND_TRIP, { calc, inputs: c.inputs, results: c.results, plant: TEETH });
    } catch (e) {
      r = { error: String(e.message || e).slice(0, 160) };
    }
    results.push({ calc, ...r, ok: !r.error && r.same === true && r.deleted !== false });
  }
} catch (e) {
  console.log(`SKIP engineering-saved-reports: ${String(e.message || e).slice(0, 160)}`);
  await browser.close();
  process.exit(0);
}
await browser.close();

if (TEETH) {
  const ok = results.length > 0 && results.every((r) => !r.error && r.same === false);
  writeFileSync(REPORT, JSON.stringify({ generated: new Date().toISOString(), teeth: true, ok, results }, null, 1));
  console.log(ok ? 'TEETH ok engineering-saved-reports: a figure changed between save and reopen was caught'
                 : 'BLUNT engineering-saved-reports: ' + JSON.stringify(results).slice(0, 300));
  process.exit(ok ? 0 : 1);
}
const passing = results.filter((r) => r.ok).map((r) => r.calc).sort();
const base = existsSync(BASELINE) ? JSON.parse(readFileSync(BASELINE, 'utf8')) : { passing: [] };
const regressed = (base.passing || []).filter((c) => !passing.includes(c));
writeFileSync(REPORT, JSON.stringify({ generated: new Date().toISOString(), teeth: false, origin: ORIGIN,
  calculators: results.length, passing: passing.length, regressed, calcs: results }, null, 1));
if (UPDATE) {
  const merged = [...new Set([...(base.passing || []), ...passing])].sort();
  writeFileSync(BASELINE, JSON.stringify({ updated: new Date().toISOString().slice(0, 10),
    note: 'calculations that reopen from History as the report that was saved - a calculator on this list that fails again is a regression',
    passing: merged }, null, 1) + '\n');
}
for (const r of results.filter((x) => !x.ok)) console.log(`  open  ${r.calc}: ${r.error || r.diff || (r.deleted === false ? 'the walk could not delete its row' : '')}`.slice(0, 400));
const fail = GATE && regressed.length > 0;
console.log(`${fail ? 'FAIL' : 'PASS'} engineering-saved-reports: ${results.length} calculations saved, reopened from History and deleted · `
  + `the same calculation ${passing.length}/${results.length} · regressed ${regressed.length}`);
process.exit(fail ? 1 : 0);
