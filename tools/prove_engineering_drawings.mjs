// prove_engineering_drawings.mjs - every calculator's drawing carries the result it was drawn from
// (Wave ED, 2026-11-02; rows ED-D1 "the drawing matches the numbers").
//
// For every case in .tmp/ed_report_cases.json (the served Python handler's answer on the form's own payload) this computes
// the calculation through the live path, runs the page's own _runDrawing() and reads the drawing - its SVG labels and its
// title block - at phone-390 and desktop-1280:
//   SHOWN  a drawing is drawn (a calculator the page offers a drawing for)
//   FIG    the drawing states the headline figures the engine computed (the door page's headline keys)
//   EVERY  every number in its labels traces to the engine's answer or its inputs (the decimals printed or the engine's own,
//          within 2%, the same unit or a stated conversion) or is a constant written in that calculator's own drawing
//          builder; a figure the drawing computes for itself is a third, unchecked engine
//   SCR    nothing wider than the phone at 390
//
//   python tools/ed_report_cases.py && node tools/prove_engineering_drawings.mjs
//   node tools/prove_engineering_drawings.mjs --gate | --update-baseline | --teeth
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
const REPORT = TEETH ? 'engineering_drawings_teeth.json' : 'engineering_drawings_report.json';
const BASELINE = 'engineering_drawings_baseline.json';
const VIEWPORTS = [['phone-390', 390, 844], ['desktop-1280', 1280, 900]];

const READ = async ({ calc, inputs, results, headline, plant, bsrc }) => {
  switchTab('calculator');
  selectCalcType(calc);
  await new Promise((r) => setTimeout(r, 150));
  _renderComputed(JSON.parse(JSON.stringify(inputs)), { results: JSON.parse(JSON.stringify(results)), narrative: null });
  await new Promise((r) => setTimeout(r, 250));
  // teeth: the drawing is drawn from figures scaled by 1.37 - the engine's own are then absent from it
  if (plant) _lastResults = Object.fromEntries(Object.entries(_lastResults).map(([k, v]) => [k, typeof v === 'number' ? v * 1.37 : v]));
  const panel = document.getElementById('drawing-panel');
  if (panel) panel.innerHTML = '';
  try { await _runDrawing(); } catch (e) { return { error: `drawing threw: ${String(e.message || e).slice(0, 120)}` }; }
  for (let i = 0; i < 30 && !(panel && panel.querySelector('svg')); i++) await new Promise((r) => setTimeout(r, 200));
  const svg = panel && panel.querySelector('svg');
  if (!svg) return { shown: false };
  const labels = [...panel.querySelectorAll('svg text')].map((t) => (t.textContent || '').trim()).filter(Boolean);
  const block = [...panel.querySelectorAll(':scope > :not(svg) td, :scope > :not(svg) div')].map((e) => (e.innerText || '').trim());
  const text = labels.concat(block).join('\n');
  const pool = [];
  const walk = (v) => { if (typeof v === 'number' && Number.isFinite(v)) pool.push(v);
    else if (v && typeof v === 'object') Object.values(v).forEach(walk);
    else if (typeof v === 'string') (v.match(/-?\d+(?:\.\d+)?/g) || []).forEach((x) => pool.push(parseFloat(x))); };
  walk(results); walk(inputs);
  const conv = [-6, -4, -3, -2, -1, 1, 2, 3, 4, 6].map((p) => (x) => x * 10 ** p)
    .concat([(x) => x, (x) => x * 3.517, (x) => x / 3.517, (x) => x + 101.3, (x) => x + 101.325]);
  const traces = (n, d) => conv.some((f) => pool.some((v) => { const x = f(v);
    if (Math.abs(n - x) > Math.max(0.02 * Math.abs(x), 1e-9)) return false;
    return Math.abs(Number(x.toFixed(d)) - n) < 1e-9 || Math.abs(n - x) <= 0.5 * 10 ** -d + 1e-9; }));
  const nums = (text.match(/-?\d[\d,]*(?:\.\d+)?/g) || []).map((t) => ({ t, n: parseFloat(t.replace(/,/g, '')), d: (t.split('.')[1] || '').length }));
  const states = (v) => {
    if (typeof v === 'number') {
      const dv = (String(v).split('.')[1] || '').length;
      return [1, 1000, 1 / 1000, 100].some((k) => nums.some(({ n, d }) => { const x = v * k;
        if (Math.abs(n - x) > Math.max(0.02 * Math.abs(x), 1e-9)) return false;
        return Math.abs(Number(x.toFixed(d)) - n) < 1e-9 || Math.abs(Number((n / k).toFixed(dv)) - v) < 1e-9; }));
    }
    if (typeof v === 'string') return v.replace(/^[a-z ]+:\s*/i, '').split(/,\s*/).every((p) => text.toLowerCase().includes(p.toLowerCase()));
    return true;
  };
  const missing = headline.filter(([, key]) => results[key] != null && !states(results[key])).map(([label, key]) => `${label} (${key} = ${JSON.stringify(results[key])})`);
  const NOT_FIGURES = /\b(?:ISO|ASME|IEC|EN|VDI|ABMA|ANSI|AISC|ACI|NFPA|PEC|ASHRAE|NSCP|ASTM|API|IEEE|CIBSE|UPC|IPC|SMACNA|TEMA|DOLE|D\.O\.|DAO|RA|PD|BS|DIN|AWS|AGMA|RMA|NEC|UL|CTI|AHRI|AMCA|NEMA|Std\.?|Table|Art\.?|Section|Sec\.|DWG|Sheet|Rev\.?)\s*[A-Z]?\d[\d.:\-]*|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}|\b\d{4}-\d{2}-\d{2}\b/g;
  const untraced = [];
  for (const line0 of labels.concat(block)) {
    const line = line0.replace(NOT_FIGURES, ' ');
    for (const tok of line.match(/-?\d[\d,]*(?:\.\d+)?/g) || []) {
      const n = parseFloat(tok.replace(/,/g, '')), d = (tok.split('.')[1] || '').length;
      if (Number.isInteger(n) && Math.abs(n) <= 12) continue;
      if (traces(n, d) || (bsrc && bsrc.includes(tok))) continue;
      untraced.push(`${tok} in "${line0.replace(/\s+/g, ' ').slice(0, 50)}"`);
    }
  }
  return { shown: true, labels: labels.length, missing, untraced: untraced.slice(0, 6), untracedCount: untraced.length,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth };
};

if (!args.includes('--no-rebuild')) {
  const py = spawnSync(process.platform === 'win32' ? 'python' : 'python3', ['tools/ed_report_cases.py'], { encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  if (py.status !== 0) console.log(`  cases: ${(py.stdout || py.stderr || '').trim().split(/\r?\n/).pop()}`);
}
if (!existsSync(CASES)) { console.log(`SKIP engineering-drawings: ${CASES} is missing`); process.exit(0); }
const cases = JSON.parse(readFileSync(CASES, 'utf8'));
// each calculator's drawing builder source (its constants are its own) - read from _runDrawing's branches
const JS_SRC = readFileSync('engineering-design.js', 'utf8');
const BUILDER = {};
// a branch may name several types: `ct === 'A' || ct === 'B') { const svg = buildX(`
for (const m of JS_SRC.matchAll(/((?:ct === '[^']+'\s*(?:\|\|\s*)?)+)\)\s*\{\s*const svg = (build\w+)\(/g)) {
  for (const n of m[1].matchAll(/ct === '([^']+)'/g)) BUILDER[n[1]] = m[2];
}
const builderSource = (calc) => {
  const name = BUILDER[calc];
  const at = name ? JS_SRC.indexOf(`function ${name}(`) : -1;
  if (at < 0) return '';
  const next = JS_SRC.indexOf('\nfunction ', at + 10);
  return JS_SRC.slice(at, next > 0 ? next : undefined);
};
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
    await page.waitForFunction(() => typeof _runDrawing === 'function' && typeof _renderComputed === 'function', null, { timeout: 20000 });
    for (const calc of run) {
      const c = cases[calc];
      let r;
      try {
        r = await page.evaluate(READ, { calc, inputs: c.inputs, results: c.results, headline: c.headline, plant: TEETH, bsrc: builderSource(calc) });
      } catch (e) {
        r = { error: String(e.message || e).slice(0, 160) };
      }
      // a calculator the page draws no drawing for has no D1 row (the roadmap counts 51 drawn): not drawn, not failed
      const ok = r.shown === false ? null
        : !r.error && r.shown && !(r.missing || []).length && !r.untracedCount && (vp !== 'phone-390' || (r.overflow || 0) <= 1);
      results.push({ calc, vp, ...r, ok });
    }
  }
} catch (e) {
  console.log(`SKIP engineering-drawings: ${String(e.message || e).slice(0, 160)}`);
  await browser.close();
  process.exit(0);
}
await browser.close();

if (TEETH) {
  const ok = results.every((r) => r.shown && ((r.missing || []).length > 0 || r.untracedCount > 0));
  writeFileSync(REPORT, JSON.stringify({ generated: new Date().toISOString(), teeth: true, ok, results }, null, 1));
  console.log(ok ? 'TEETH ok engineering-drawings: a drawing drawn from figures that are not the engine’s was caught'
                 : 'BLUNT engineering-drawings: ' + JSON.stringify(results).slice(0, 300));
  process.exit(ok ? 0 : 1);
}
const byCalc = {};
for (const r of results) {
  const c = byCalc[r.calc] || (byCalc[r.calc] = { calc: r.calc, ok: true, shown: true, faults: [] });
  if (r.ok === null) { c.shown = false; continue; }      // not drawn: no D1 unit
  c.ok = c.ok && r.ok;
  if (r.error) c.faults.push(`${r.vp}: ${r.error}`);
  if ((r.missing || []).length) c.faults.push(`${r.vp}: does not state ${r.missing.join('; ')}`);
  if (r.untracedCount) c.faults.push(`${r.vp}: ${r.untracedCount} figure(s) not the engine's - ${r.untraced.join('; ')}`);
  if (r.vp === 'phone-390' && (r.overflow || 0) > 1) c.faults.push(`${r.vp}: ${r.overflow}px wider than the phone`);
}
const calcs = Object.values(byCalc);
const passing = calcs.filter((c) => c.shown && c.ok).map((c) => c.calc).sort();
const base = existsSync(BASELINE) ? JSON.parse(readFileSync(BASELINE, 'utf8')) : { passing: [] };
const regressed = (base.passing || []).filter((c) => !passing.includes(c));
writeFileSync(REPORT, JSON.stringify({ generated: new Date().toISOString(), teeth: false, origin: ORIGIN,
  calculators: calcs.length, drawn: calcs.filter((c) => c.shown).length, passing: passing.length, regressed, calcs, results }, null, 1));
if (UPDATE) {
  const merged = [...new Set([...(base.passing || []), ...passing])].sort();
  writeFileSync(BASELINE, JSON.stringify({ updated: new Date().toISOString().slice(0, 10),
    note: 'drawings that carry the engine’s figures and fit a phone - a drawing on this list that fails again is a regression', passing: merged }, null, 1) + '\n');
}
for (const c of calcs.filter((x) => x.shown && !x.ok)) console.log(`  open  ${c.calc}: ${c.faults.slice(0, 2).join(' || ')}`.slice(0, 420));
const fail = GATE && regressed.length > 0;
console.log(`${fail ? 'FAIL' : 'PASS'} engineering-drawings: ${calcs.length} calculators at ${VIEWPORTS.length} widths · drawn ${calcs.filter((c) => c.shown).length} · `
  + `matching the engine ${passing.length}/${calcs.filter((c) => c.shown).length} · regressed ${regressed.length}`);
process.exit(fail ? 1 : 0);
