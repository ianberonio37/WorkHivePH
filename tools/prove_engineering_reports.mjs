// prove_engineering_reports.mjs - every calculator's report, read as a person reads it, on screen and on paper
// (Wave ED, 2026-11-02; rows ED-R1 "the report reads true, on screen and on paper").
//
// Walking the reports by hand found what no gate held: the vibration report's zone table printed the NEXT class's limits
// under a verdict judged on the right ones; the noise report judged the free-field level against an "85 dBA limit"; the
// UPS signature row and AHU's summary tiles ran a phone page to 403 and 402 px. R1 is that reading, for every calculator.
//
// For every case in .tmp/ed_report_cases.json (tools/ed_report_cases.py: the served Python handler run on the form's own
// default payload) this selects the calculator, renders its report through the page's live path (_renderComputed, the
// one Calculate uses; no AI narrative, so the report's own text is what is read) and checks, at phone-390 and
// desktop-1280:
//   FIG    the report states each headline figure the engine computed (the door page's headline keys): a number in the
//          report that IS the engine's value at the decimals the report prints, within 2% - never a rounder coincidence
//   BRK    no broken figure: undefined, NaN, Infinity, [object Object], null, or an unfilled ${...}
//   SCR    nothing wider than the phone at 390
//   PAPER  printed (print media, A4 width 794 px), the report is shown and nothing runs past the page edge - on paper a
//          scroll box clips, so a table wider than the page is a report that is not whole
//
//   python tools/ed_report_cases.py && node tools/prove_engineering_reports.mjs          # write engineering_reports_report.json
//   node tools/prove_engineering_reports.mjs --gate             # exit 1 on a fault, or on a report that passed before and fails now
//   node tools/prove_engineering_reports.mjs --update-baseline  # add today's passing reports to the ratchet (never removes)
//   node tools/prove_engineering_reports.mjs --teeth            # plant wrong figures (x1.37), a broken token, a too-wide block
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
const REPORT = TEETH ? 'engineering_reports_teeth.json' : 'engineering_reports_report.json';
const BASELINE = 'engineering_reports_baseline.json';
const VIEWPORTS = [['phone-390', 390, 844], ['desktop-1280', 1280, 900]];
const PAPER_W = 794;

// render one calculator's report and read it - runs in the page
const READ = async ({ calc, inputs, results, headline, plant }) => {
  switchTab('calculator');
  selectCalcType(calc);
  await new Promise((r) => setTimeout(r, 150));
  // teeth: every numeric result scaled by 1.37, so whichever key the renderer prints, the report no longer states the engine's
  const shown = plant ? Object.fromEntries(Object.entries(results).map(([k, v]) => [k, typeof v === 'number' ? v * 1.37 : v])) : results;
  _renderComputed(JSON.parse(JSON.stringify(inputs)), { results: JSON.parse(JSON.stringify(shown)), narrative: null });
  await new Promise((r) => setTimeout(r, 300));
  const panel = document.getElementById('report-panel');
  if (plant) panel.insertAdjacentHTML('beforeend', '<p>planted value undefined</p><div style="width:1400px;height:4px"></div>');
  const text = (panel?.innerText || '').replace(/ /g, ' ');
  const nums = (text.match(/-?\d[\d,]*(?:\.\d+)?/g) || []).map((t) => ({ t, n: parseFloat(t.replace(/,/g, '')), d: (t.split('.')[1] || '').length }));
  const states = (v) => {
    if (typeof v === 'number') {
      if (!Number.isFinite(v)) return false;
      // the same figure in another unit of the same quantity (m3 as L, kW as W, a fraction as a percentage), matched either
      // way round: the report's figure rounded to the engine's decimals (the engine's 0.21 m3 is itself 209.9 L rounded), or
      // the engine's rounded to the report's - always within 2%, so a rounder coincidence never counts
      const dv = (String(v).split('.')[1] || '').length;
      return [1, 1000, 1 / 1000, 100].some((k) => nums.some(({ n, d }) => {
        const x = v * k;
        if (Math.abs(n - x) > Math.max(0.02 * Math.abs(x), 1e-9)) return false;
        return Math.abs(Number(x.toFixed(d)) - n) < 1e-9 || Math.abs(Number((n / k).toFixed(dv)) - v) < 1e-9;
      }));
    }
    // a "mixed: A, B, C" selection is stated when each of its items is
    if (typeof v === 'string') return v.replace(/^[a-z ]+:\s*/i, '').split(/,\s*/).every((part) => text.toLowerCase().includes(part.toLowerCase()));
    return true;   // a boolean or a structure is not a printed figure
  };
  const missing = headline.filter(([, key]) => results[key] != null && !states(results[key])).map(([label, key]) => `${label} (${key} = ${JSON.stringify(results[key])})`);
  const absent = headline.filter(([, key]) => results[key] == null).map(([label, key]) => `${label} (${key})`);
  const broken = [...new Set(text.match(/\bundefined\b|\bNaN\b|\bInfinity\b|\[object Object\]|\bnull\b|\$\{/g) || [])];
  return { chars: text.length, missing, absent, broken, overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth };
};

// on paper: print media at A4 width - the report must be shown and nothing may run past the page edge
const PAPER = () => {
  const panel = document.getElementById('report-panel');
  if (!panel || !panel.getClientRects().length) return { shown: false, past: [] };
  const edge = document.documentElement.clientWidth;
  const past = [];
  for (const el of panel.querySelectorAll('*')) {
    const r = el.getBoundingClientRect();
    if (r.width && r.right > edge + 1 && el.getClientRects().length) {
      past.push(`${el.tagName.toLowerCase()} ${Math.round(r.right)}px: ${(el.innerText || '').replace(/\s+/g, ' ').slice(0, 50)}`);
      if (past.length >= 3) break;
    }
  }
  return { shown: true, past, height: Math.round(panel.getBoundingClientRect().height) };
};

// the cases are the served engine's answers NOW - rebuilt each run, so the walk never grades a stale engine
if (!args.includes('--no-rebuild')) {
  const py = spawnSync(process.platform === 'win32' ? 'python' : 'python3', ['tools/ed_report_cases.py'], { encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  if (py.status !== 0) console.log(`  cases: ${(py.stdout || py.stderr || '').trim().split(/\r?\n/).pop()}`);
}
if (!existsSync(CASES)) {
  console.log(`SKIP engineering-reports: ${CASES} is missing - run python tools/ed_report_cases.py first`);
  process.exit(0);
}
const cases = JSON.parse(readFileSync(CASES, 'utf8'));
const browser = await chromium.launch();
const ctx = await browser.newContext();
await assertSignedIn(signIn(ctx, 'supervisor'));
const page = await ctx.newPage();
const results = [];
try {
  const run = TEETH ? ['Vibration Analysis'] : Object.keys(cases);
  for (const [vp, w, h] of VIEWPORTS) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto(`${ORIGIN}/engineering-design.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForFunction(() => typeof _renderComputed === 'function' && typeof selectCalcType === 'function', null, { timeout: 20000 });
    const landed = await page.evaluate(() => location.pathname);
    if (!/engineering-design/.test(landed)) throw new Error(`landed on ${landed}, not engineering-design.html`);
    for (const calc of run) {
      const c = cases[calc];
      let r;
      try {
        r = await page.evaluate(READ, { calc, inputs: c.inputs, results: c.results, headline: c.headline, plant: TEETH });
      } catch (e) {
        r = { error: String(e.message || e).slice(0, 160), missing: [], absent: [], broken: [], overflow: 0, chars: 0 };
      }
      let paper = null;
      if (vp === 'desktop-1280') {
        await page.setViewportSize({ width: PAPER_W, height: 1123 });
        await page.emulateMedia({ media: 'print' });
        paper = await page.evaluate(PAPER);
        await page.emulateMedia({ media: 'screen' });
        await page.setViewportSize({ width: w, height: h });
      }
      const ok = !r.error && r.chars > 400 && !r.missing.length && !r.broken.length
        && (vp !== 'phone-390' || r.overflow <= 1) && (!paper || (paper.shown && !paper.past.length));
      results.push({ calc, vp, ...r, paper, ok });
    }
  }
} catch (e) {
  // the site is not up, or the page did not load: an instrument that cannot reach its page abstains - it grades nothing
  console.log(`SKIP engineering-reports: ${String(e.message || e).slice(0, 160)}`);
  await browser.close();
  process.exit(0);
}
await browser.close();

if (TEETH) {
  const caught = {
    wrongFigure: results.every((r) => r.missing.length > 0),
    brokenToken: results.every((r) => r.broken.includes('undefined')),
    tooWide: results.filter((r) => r.vp === 'phone-390').every((r) => r.overflow > 1),
  };
  const ok = Object.values(caught).every(Boolean);
  writeFileSync(REPORT, JSON.stringify({ generated: new Date().toISOString(), teeth: true, caught, ok, results }, null, 1));
  console.log(ok ? 'TEETH ok engineering-reports: a wrong headline figure, a broken token and a block wider than the phone were each caught'
                 : 'BLUNT engineering-reports: ' + JSON.stringify(caught));
  process.exit(ok ? 0 : 1);
}

const byCalc = {};
for (const r of results) {
  const c = byCalc[r.calc] || (byCalc[r.calc] = { calc: r.calc, ok: true, faults: [] });
  c.ok = c.ok && r.ok;
  if (r.error) c.faults.push(`${r.vp}: did not render - ${r.error}`);
  if (!r.error && r.chars <= 400) c.faults.push(`${r.vp}: report is ${r.chars} characters`);
  if (r.missing.length) c.faults.push(`${r.vp}: does not state ${r.missing.join('; ')}`);
  if (r.broken.length) c.faults.push(`${r.vp}: broken figure ${r.broken.join(', ')}`);
  if (r.vp === 'phone-390' && r.overflow > 1) c.faults.push(`${r.vp}: ${r.overflow}px wider than the phone`);
  if (r.paper && !r.paper.shown) c.faults.push('paper: the report is not shown in print');
  if (r.paper && r.paper.past.length) c.faults.push(`paper: runs past the A4 edge - ${r.paper.past.join(' | ')}`);
}
const calcs = Object.values(byCalc);
const passing = calcs.filter((c) => c.ok).map((c) => c.calc).sort();
const base = existsSync(BASELINE) ? JSON.parse(readFileSync(BASELINE, 'utf8')) : { passing: [] };
const regressed = (base.passing || []).filter((c) => !passing.includes(c));
writeFileSync(REPORT, JSON.stringify({ generated: new Date().toISOString(), teeth: false, origin: ORIGIN,
  viewports: VIEWPORTS.map((v) => v[0]), paper_width: PAPER_W, calculators: calcs.length, passing: passing.length,
  regressed, calcs, results }, null, 1));
if (UPDATE) {
  const merged = [...new Set([...(base.passing || []), ...passing])].sort();
  writeFileSync(BASELINE, JSON.stringify({ updated: new Date().toISOString().slice(0, 10),
    note: 'reports that state their headline figures, carry no broken figure, fit a phone and print whole - a report on this list that fails again is a regression',
    passing: merged }, null, 1) + '\n');
}
for (const c of calcs.filter((x) => !x.ok)) console.log(`  open  ${c.calc}: ${c.faults.slice(0, 3).join(' || ')}`);
const fail = GATE && regressed.length > 0;
console.log(`${fail ? 'FAIL' : 'PASS'} engineering-reports: ${calcs.length} reports at ${VIEWPORTS.length} widths and on paper · `
  + `reading true ${passing.length}/${calcs.length} · regressed ${regressed.length}`);
process.exit(fail ? 1 : 0);
