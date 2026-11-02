// prove_engineering_boms.mjs - every calculator's bill of materials and scope are this result's, and survive edit and download
// (Wave ED, 2026-11-02; rows ED-B1 "the bill of materials and scope are this result's").
//
// The BOM/SOW is an AI agent (supabase/functions/engineering-bom-sow, the free-tier chain in _shared/ai-chain.ts) fed by a
// prompt each calculator's agent builds from the calculation. A probe of four found what no gate held: the transformer's
// prompt asked the model for "MCCB rated minimum 125% of I2" and it chose 125 A for a 144 A secondary; the fire pump's
// prompt said "jockey approx. 10% of main pump flow" while the engine had computed 28.4 L/min (1%); the boiler agent read
// inputs.feedwater_temp / tds_max / tds_makeup, which the form never sends, so every boiler BOM used 80 °C and 3500 ppm.
//
// For every BOM-supported case in .tmp/ed_report_cases.json (the served engine on the form's own payload), as the signed-in
// walker at phone-390, inside engineering-design.html:
//   SENT   the body the page sends the agent is captured at the network (the real call goes through)
//   GROUND every value the agent reads from that body (each `const` and each ${...} in its source) has at least one key of
//          its fallback chain present - a chain with none present means the BOM was written from the code's default
//   BRK    no BOM or SOW field says N/A, undefined, NaN, null, [object Object] or an unfilled ${...}
//   FIG    the engine's rating (the case's first headline figure) is stated in the BOM or the SOW
//   STD    the SOW names a standard
//   EDIT   a quantity edited in the checklist reaches Generate Documents' table and the downloaded CSV
//   SCR    the checklist and the documents fit the phone
//
//   node tools/prove_engineering_boms.mjs [--gate] [--update-baseline] [--only "<calc>"] [--static]
//   --static re-reads the last receipt's captured bodies against the agent source (no browser, no AI call)
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { spawnSync } from 'child_process';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const UPDATE = args.includes('--update-baseline');
const TEETH = args.includes('--teeth');            // a --static re-read with three planted defects; writes its own file
const STATIC = args.includes('--static') || TEETH;
// --only "A,B": walk those calculators and MERGE them into the last receipt (each result keeps the time it was walked)
const ONLY = args.includes('--only') ? args[args.indexOf('--only') + 1].split(',').map((x) => x.trim()) : null;
const CASES = '.tmp/ed_report_cases.json';
const REPORT = 'engineering_boms_report.json';
const TEETH_OUT = 'engineering_boms_teeth.json';
const BASELINE = 'engineering_boms_baseline.json';
const AGENT_SRC = 'supabase/functions/engineering-bom-sow/index.ts';
const WALKER = 'b2c280aa-9b01-4dcd-8e8f-00a2ef06f159';   // leandromarquez - the supervisor walker's solo AI bucket

// ── GROUND, from the agent's own source ───────────────────────────────────────────────────────────────────────────
// teeth: the transformer agent reads a key the engine never returns, as the boiler agent did
const src = TEETH ? readFileSync(AGENT_SRC, 'utf8').replace('results.I2_full_load_A', 'results.I2_planted_phantom')
                  : readFileSync(AGENT_SRC, 'utf8');
const agentOf = {};
// a route may name two calculators (`calc_type === "Gear / Belt Drive" || calc_type === "V-Belt Drive Design"`)
for (const m of src.matchAll(/if \(([^{]*?calc_type === "[^{]*?)\)\s*\{\s*result = await (\w+)\(/g)) {
  for (const c of m[1].matchAll(/calc_type === "([^"]+)"/g)) agentOf[c[1]] = m[2];
}
const bodyOf = (fn) => {
  const a = src.indexOf(`async function ${fn}(`);
  if (a < 0) return '';
  const b = src.indexOf('\nasync function ', a + 10);
  return src.slice(a, b < 0 ? undefined : b);
};
// each expression that reads the body: a `const x = ...;` and each ${...} placeholder
const readsOf = (body) => {
  const out = [];
  for (const m of body.matchAll(/const\s+(\w+)\s*=\s*([\s\S]*?);\s*\n/g)) out.push({ at: m[1], expr: m[2] });
  for (const m of body.matchAll(/\$\{([^{}]*)\}/g)) out.push({ at: '${' + m[1].trim().slice(0, 40) + '}', expr: m[1] });
  return out.map((r) => ({ ...r, keys: [...r.expr.matchAll(/\b(inputs|results)\.(\w+)/g)].map((k) => [k[1], k[2]]) })).filter((r) => r.keys.length);
};
const has = (o, k) => o && Object.prototype.hasOwnProperty.call(o, k) && o[k] !== null && o[k] !== undefined && o[k] !== '';
const groundOf = (calc, sent) => {
  const fn = agentOf[calc];
  if (!fn) return [{ at: '(router)', why: `no agent is routed for "${calc}"` }];
  const faults = [];
  for (const r of readsOf(bodyOf(fn))) {
    if (r.keys.some(([o, k]) => has(o === 'inputs' ? sent.calc_inputs : sent.calc_results, k))) continue;
    const dflt = (r.expr.match(/(?:\?\?|\|\|)\s*("[^"]*"|'[^']*'|-?[\d.]+|true|false)\s*\)?\s*$/) || [])[1];
    faults.push({ at: r.at, keys: r.keys.map(([o, k]) => `${o}.${k}`).join(' ?? '), used: dflt ?? '(undefined)' });
  }
  return faults;
};

// a value the receipt reads as recorded-by-decision rather than a fault: an expression that belongs to another mode of the
// same calculator (the agent reads both modes' keys; only one is sent). Each entry names its reason.
const OTHER_MODE = 'a key of another mode of this calculator; the case walked does not send it and the prompt does not print it';
const RECORDED = {
  'HVAC Cooling Load': { voltage: 'the form has no supply voltage; a split unit in the Philippines is 230 V 1-phase 60 Hz, which the BOM states as its basis' },
  'Boiler System': { supplyTemp: OTHER_MODE + ' (hot-water boiler; the case is steam)', returnTemp: OTHER_MODE, deltaT: OTHER_MODE,
                     hwPressure: OTHER_MODE, flowLhr: OTHER_MODE },
  'Solar PV System': { battKWh: OTHER_MODE + ' (off-grid/hybrid battery; the case is grid-tied and the engine returns none)', battAh: OTHER_MODE },
  'Water Softener Sizing': { saltType: 'the form has no salt choice; the BOM states NaCl as its basis', resinType: 'the form has no resin choice; Na-form strong-acid cation resin is the stated basis',
                             regenSystem: 'the form has no regeneration control; timer-initiated is the stated basis' },
  'Bearing Life (L10)': { bearingNo: 'a blank bearing number means the bearing is "to be selected from the manufacturer catalog", which the BOM says' },
  'Heat Exchanger': { prompt: 'the form has no design pressure; the pressure gauges default to a 0-20 bar range', '${Math.ceil(Number(inputs.design_p': 'as above: the gauge range' },
  'Vibration Analysis': { prompt: 'the form has no pipe pressure; the flexible connector is specified at its 10 bar floor', '${Math.max(10, Math.round(Number(i': 'as above' },
  'Noise / Acoustics': { dose: OTHER_MODE + ' (the TWA dose mode)', barrierIL: OTHER_MODE + ' (the barrier mode)',
                         exposedWorkers: 'the form has no headcount; the scope says every exposed worker, the count to be confirmed on site',
                         '${String(inputs.exposed_workers_count)': 'as above: the count is printed only when given',
                         workerN: 'as above: with no headcount the PPE line is one set per exposed worker' },
  'V-Belt Drive Design': { module: OTHER_MODE + ' (the gear module; the case is a V-belt drive)', chainNo: OTHER_MODE + ' (the chain number)' },
  'Gear / Belt Drive': { module: OTHER_MODE + ' (the gear module)', chainNo: OTHER_MODE + ' (the chain number)' },
  'Beam / Column Design': { dcrA: OTHER_MODE + ' (column)', phiPnKN: OTHER_MODE + ' (column)', axialOk: OTHER_MODE + ' (column)',
                            '${results.fc_MPa': OTHER_MODE + ' (reinforced concrete; the case is a steel beam)', '${results.fy_MPa': OTHER_MODE,
                            '${results.As_mm2': OTHER_MODE, '${results.stirrup_dia_mm': 'the form has no stirrup size; 10 mm is the stated basis',
                            '${results.tie_dia_mm': 'the form has no tie size; 10 mm is the stated basis' },
};
const recorded = (calc, at) => Object.keys(RECORDED[calc] || {}).some((k) => at === k || at.startsWith(k));

// ── the walk, in the page ─────────────────────────────────────────────────────────────────────────────────────────
const GEN = async ({ calc, inputs, results }) => {
  switchTab('calculator');
  selectCalcType(calc);
  await new Promise((r) => setTimeout(r, 150));
  _renderComputed(JSON.parse(JSON.stringify(inputs)), { results: JSON.parse(JSON.stringify(results)), narrative: null });
  window.__toasts = [];
  if (!window.__wired) {
    window.__wired = true;
    const st = window.showToast;
    window.showToast = (m, ...a) => { window.__toasts.push(String(m)); try { return st(m, ...a); } catch (e) { return undefined; } };
  }
  _bomItems = []; _sowSections = [];
  document.getElementById('bom-checklist-panel')?.classList.add('hidden');
  document.getElementById('bom-preview')?.classList.add('hidden');
  document.getElementById('bom-trigger')?.classList.remove('hidden');
  await generateBomSowChecklist();
  const panel = document.getElementById('bom-checklist-panel');
  const wide = (el) => (el && !el.classList.contains('hidden') ? el.scrollWidth : 0);
  return { toast: window.__toasts.join(' | ').slice(0, 300), bom: JSON.parse(JSON.stringify(_bomItems)),
           sow: JSON.parse(JSON.stringify(_sowSections)), checklistW: wide(panel), vw: document.documentElement.clientWidth };
};
// edit the first item's quantity in the checklist the way a person does, then Generate Documents
const EDIT = async ({ qty }) => {
  const inp = document.querySelector('#bom-items-list .bom-checklist-item input[type=number]');
  if (!inp) return { ok: false, why: 'no quantity input in the checklist' };
  inp.value = String(qty);
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  generateDocuments();
  await new Promise((r) => setTimeout(r, 400));
  const docs = document.getElementById('bom-preview');
  if (!docs || docs.classList.contains('hidden')) return { ok: false, why: 'Generate Documents showed no documents' };
  // the documents table prints each figure in an input (innerText never shows an input's value)
  const q0 = docs.querySelector('#bom-table-preview tbody tr input[type=number]');
  const inTable = !!q0 && Number(q0.value) === qty;
  // and a person may correct a quantity in the documents themselves: that edit must reach the downloads too
  if (q0) { q0.value = String(qty + 4); q0.dispatchEvent(new Event('input', { bubbles: true })); }
  const over = [...docs.querySelectorAll('*')].filter((el) => el.getBoundingClientRect().right > document.documentElement.clientWidth + 1
    && !el.closest('.table-wrap')).map((el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : '')).slice(0, 4);
  return { ok: true, inTable, docEdit: qty + 4, docsW: docs.scrollWidth, over, item0: _bomItems[0]?.qty };
};

const BRK = /\bN\/A\b|\bundefined\b|\bNaN\b|\bnull\b|\[object Object\]|\$\{/;
const STD = /\b(NFPA|ASHRAE|PEC|IEEE|IEC|ISO|ASME|ASTM|AWS|PSME|NEC|UPC|NPC|IPC|DOLE|BFP|AWWA|DENR|DPWH|NSCP|AISC|ACI|SMACNA|CTI|AHRI|EN|BS|DIN|JIS|AGMA|API|TEMA|OSHA|ANSI|UL|NEMA|ERC|Philippine (?:Electrical|Plumbing|Fire|Grid|Mechanical) Code|RA \d+)\b/;
const numsIn = (s) => (String(s).match(/-?\d[\d,]*(?:\.\d+)?/g) || []).map((t) => ({ n: parseFloat(t.replace(/,/g, '')), d: (t.split('.')[1] || '').length }));
const statesFig = (text, v) => {
  if (typeof v !== 'number' || !Number.isFinite(v) || v === 0) return true;
  // the same quantity in a unit a BOM uses: kW/hp, kW/TR, k-prefix, L/min-m3/h, bar-kPa-psi, CFM-m3/h, m3/s and L/s-m3/h
  const forms = [v, v * 1.341, v / 1.341, v / 3.517, v * 3.517, v * 1000, v / 1000, v / 16.667, v * 16.667, v * 100,
                 v * 14.504, v * 1.699, v / 1.699, v * 3600, v / 3600, v * 3.6, v / 3.6];
  return numsIn(text).some(({ n, d }) => forms.some((f) => Math.abs(n - Number(f.toFixed(d))) < 1e-9 || Math.abs(n - f) <= Math.abs(f) * 0.01));
};

// ── run ───────────────────────────────────────────────────────────────────────────────────────────────────────────
const resetQuota = () => spawnSync('docker', ['exec', 'supabase_db_workhive', 'psql', '-U', 'postgres', '-tAc',
  `update public.ai_rate_limits set call_count = 0, day_count = 0 where hive_id = '${WALKER}'; ` +
  `update public.ai_user_rate_limits set call_count = 0, day_count = 0 where user_id = '${WALKER}';`], { encoding: 'utf8' });

let results = [];
let walkedAt = new Date().toISOString();   // a --static re-read keeps the walk's own time
if (STATIC) {
  if (!existsSync(REPORT)) { console.log(`SKIP engineering-boms: no ${REPORT} to re-read`); process.exit(0); }
  const last = JSON.parse(readFileSync(REPORT, 'utf8'));
  walkedAt = last.generated;
  results = last.results.map((r) => ({ ...r, ground: r.sent ? groundOf(r.calc, r.sent) : r.ground }));
} else {
  if (!existsSync(CASES)) {
    const py = spawnSync(process.platform === 'win32' ? 'python' : 'python3', ['tools/ed_report_cases.py'], { encoding: 'utf8', env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
    if (py.status !== 0) { console.log(`SKIP engineering-boms: ${CASES} could not be built`); process.exit(0); }
  }
  const cases = JSON.parse(readFileSync(CASES, 'utf8'));
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ acceptDownloads: true });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const page = await ctx.newPage();
  page.on('dialog', (d) => d.accept().catch(() => {}));
  let sent = null;
  await page.route('**/functions/v1/engineering-bom-sow**', async (route) => {
    try { sent = JSON.parse(route.request().postData() || '{}'); } catch (e) { sent = null; }
    await route.continue();
  });
  try {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${ORIGIN}/engineering-design.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForFunction(() => typeof _renderComputed === 'function' && typeof generateBomSowChecklist === 'function', null, { timeout: 20000 });
    const calcs = Object.keys(cases).filter((c) => agentOf[c] && (!ONLY || ONLY.includes(c)));
    let n = 0;
    for (const calc of calcs) {
      if (n++ % 25 === 0) resetQuota();             // the solo bucket is 30 an hour: a full walk is two buckets
      sent = null;
      const c = cases[calc];
      let r;
      const textOf = (x) => [...x.bom.map((i) => `${i.description} ${i.specification} ${i.qty} ${i.unit} ${i.remarks || ''}`),
                             ...x.sow.map((s) => `${s.title} ${s.content}`)].join('\n');
      const [hl0, hk0] = (c.headline || [])[0] || [];
      const contentOk = (x) => { const t = textOf(x); return x.bom.length && STD.test(t) && !BRK.test(t) && (!hk0 || statesFig(t, c.results[hk0])); };
      try {
        r = await page.evaluate(GEN, { calc, inputs: c.inputs, results: c.results });
        // the words are a model's: a content fault (rating, standard, a broken value) is regenerated once before it counts,
        // so the ratchet holds the agent's prompt, not one sample of it. Grounding, edit and fit are never retried.
        if (!contentOk(r)) { sent = null; r = await page.evaluate(GEN, { calc, inputs: c.inputs, results: c.results }); r.retried = true; }
      } catch (e) { results.push({ calc, error: String(e.message || e).slice(0, 200) }); continue; }
      const text = textOf(r);
      const out = { calc, agent: agentOf[calc], sent, toast: r.toast, retried: !!r.retried, bomN: r.bom.length, sowN: r.sow.length, bom: r.bom, sow: r.sow,
                    ground: sent ? groundOf(calc, sent) : [{ at: '(network)', why: 'no request reached engineering-bom-sow' }] };
      out.brk = text.split('\n').filter((l) => BRK.test(l)).map((l) => l.slice(0, 160)).slice(0, 8);
      const [hl, hk, hu] = (c.headline || [])[0] || [];
      out.fig = hk ? { label: hl, key: hk, unit: hu, value: c.results[hk], stated: statesFig(text, c.results[hk]) } : null;
      out.std = (text.match(STD) || [])[0] || null;
      out.checklistOver = r.checklistW > r.vw + 1 ? r.checklistW : 0;
      if (r.bom.length) {
        const qty = 37;
        let csv = '';
        const e = await page.evaluate(EDIT, { qty });
        try {
          const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 8000 }), page.evaluate(() => downloadBomCsv())]);
          const p = await dl.path();
          csv = p ? readFileSync(p, 'utf8') : '';
        } catch (err) { csv = ''; }
        const firstRow = csv.split('\n').find((l) => /^"?1"?,/.test(l)) || '';
        out.edit = { ...e, inCsv: new RegExp(`,${e.docEdit}(,|$)`).test(firstRow), csvRow1: firstRow.slice(0, 160), csvRows: csv.split('\n').length };
        out.docsOver = e.docsW > r.vw + 1 ? e.docsW : 0;
      }
      out.at = new Date().toISOString();
      results.push(out);
      console.log(`  ${calc}: bom ${r.bom.length} sow ${r.sow.length}${out.ground.length ? ` · ${out.ground.length} unread` : ''}${out.brk.length ? ` · ${out.brk.length} broken` : ''}${out.fig && !out.fig.stated ? ' · rating not stated' : ''}${r.toast ? ' · ' + r.toast.slice(0, 80) : ''}`);
    }
  } catch (e) {
    console.log(`SKIP engineering-boms: ${String(e.message || e).slice(0, 160)}`);
    await browser.close();
    process.exit(0);
  }
  await browser.close();
  resetQuota();
}

const faultsOf = (r) => {
  if (r.error) return [r.error];
  const f = [];
  if (!r.bomN || !r.sowN) f.push(`GEN: no BOM/SOW (${r.toast || 'empty'})`);
  for (const g of r.ground || []) if (!recorded(r.calc, g.at)) f.push(`GROUND: ${g.at} reads ${g.keys || ''}${g.why || ''} - none sent, so the BOM used ${g.used ?? 'nothing'}`);
  for (const b of r.brk || []) f.push(`BRK: ${b}`);
  if (r.fig && !r.fig.stated) f.push(`FIG: the ${r.fig.label} (${r.fig.value} ${r.fig.unit}) is not stated`);
  if (r.bomN && !r.std) f.push('STD: the SOW names no standard');
  if (r.edit && !r.edit.ok) f.push(`EDIT: ${r.edit.why}`);
  else if (r.edit && !r.edit.inTable) f.push('EDIT: a quantity edited in the checklist is not the one in the documents table');
  else if (r.edit && !r.edit.inCsv) f.push(`EDIT: a quantity corrected in the documents table (${r.edit.docEdit}) is not in the downloaded CSV (row 1: ${r.edit.csvRow1})`);
  if (r.checklistOver) f.push(`SCR: the checklist is ${r.checklistOver} px on a 390 px phone`);
  if (r.docsOver) f.push(`SCR: the documents are ${r.docsOver} px on a 390 px phone (${(r.edit?.over || []).join(', ')})`);
  return f;
};
if (TEETH) {
  // and a broken figure in one BOM line, and a documents edit that never reached the CSV
  const a = results.find((r) => r.calc === 'Pump Sizing (TDH)'), b = results.find((r) => r.calc === 'Boiler System');
  if (a && a.bom[0]) { a.bom[0].specification += ' rated undefined kW'; a.brk = [a.bom[0].specification]; }
  if (b && b.edit) b.edit = { ...b.edit, inCsv: false };
}
for (const r of results) r.faults = faultsOf(r);
if (TEETH) {
  const by = (calc, k) => (results.find((r) => r.calc === calc)?.faults || []).some((f) => f.startsWith(k));
  const saw = { ground: by('Transformer Sizing', 'GROUND'), brk: by('Pump Sizing (TDH)', 'BRK'), edit: by('Boiler System', 'EDIT') };
  const ok = saw.ground && saw.brk && saw.edit;
  writeFileSync(TEETH_OUT, JSON.stringify({ generated: new Date().toISOString(), teeth: true, ok, saw }, null, 1));
  console.log(ok ? 'TEETH ok engineering-boms: named the phantom key, the broken figure and the edit the CSV lost'
                 : 'BLUNT engineering-boms: ' + JSON.stringify(saw));
  process.exit(ok ? 0 : 1);
}
if (ONLY && !STATIC && existsSync(REPORT)) {
  const prior = JSON.parse(readFileSync(REPORT, 'utf8')).results || [];
  results = [...prior.filter((r) => !results.some((x) => x.calc === r.calc)), ...results];
  for (const r of results) r.faults = faultsOf(r);
}
const passing = results.filter((r) => !r.faults.length).map((r) => r.calc).sort();
const base = existsSync(BASELINE) ? JSON.parse(readFileSync(BASELINE, 'utf8')) : { passing: [] };
const regressed = (base.passing || []).filter((c) => results.some((r) => r.calc === c) && !passing.includes(c));
writeFileSync(REPORT, JSON.stringify({ generated: walkedAt, origin: ORIGIN, calculators: results.length,
  passing: passing.length, regressed, results }, null, 1));
if (UPDATE) {
  const merged = [...new Set([...(base.passing || []), ...passing])].sort();
  writeFileSync(BASELINE, JSON.stringify({ updated: new Date().toISOString().slice(0, 10),
    note: 'calculators whose BOM/SOW is written from what the page sends, states the rating and a standard, and keeps an edit to the CSV', passing: merged }, null, 1) + '\n');
}
const by = {};
for (const r of results) for (const f of r.faults) { const k = f.split(':')[0]; by[k] = (by[k] || 0) + 1; }
for (const r of results.filter((x) => x.faults.length).slice(0, 60)) console.log(`  open  ${r.calc}: ${r.faults.slice(0, 3).join(' | ')}`.slice(0, 420));
const fail = GATE && regressed.length > 0;
console.log(`${fail ? 'FAIL' : 'PASS'} engineering-boms: ${results.length} BOM/SOW · faults ${JSON.stringify(by)} · holding ${passing.length}/${results.length} · regressed ${regressed.length}`);
process.exit(fail ? 1 : 0);
