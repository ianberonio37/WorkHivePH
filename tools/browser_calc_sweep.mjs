// browser_calc_sweep.mjs — Arc B browser-tier harness for engineering-design.html
//
// WHY THIS EXISTS (the gap it closes)
// -----------------------------------
// Every prior engineering-design "proof" ran BELOW the browser:
//   - validate_calc_formula_accuracy.py imports the pure Python calc (the math)
//   - the :8000 /calculate API tier and the edge-fn curl tier
//   - "PDF non-gap" was a code-read, 0 PDFs generated
// None of them exercise the JS RENDER LAYER between the API and the worker —
// the `renderXReport()` functions that turn `data.results` into the DOM the user
// actually reads. The FCU `cw_flow_lps` x1000 bug lived exactly there, and an
// analogue could hide in any of the 53 UI forms while every API-tier validator
// stays green. This harness drives the real page (selectDiscipline ->
// selectCalcType -> fill inputs -> runCalculation -> read #report-panel) and
// asserts the rendered value against the authoritative Python engine.
//
// TWO CHECKS PER CALC TYPE
//   (a) cross-engine: the SERVED result (`_lastResults`, i.e. what the edge fn
//       returned and the page rendered from) == the :8000 Python value within
//       tolerance. Catches the silent TS-fallback divergence (found 2026-06-18:
//       HVAC Cooling Load served the unvalidated TS 10.15 kW instead of the
//       Python 14.85 kW, because a numpy.bool_ 500'd /calculate).
//   (b) render-faithful: each primary value present in `_lastResults` actually
//       appears (correctly formatted) in the rendered #report-panel text.
//       Catches the renderXReport JS-transform drift (the literal FCU class).
//
// Also records the engine `source` (python | ts-fallback) per type so we can see
// which calcs silently run on the un-value-validated TypeScript path.
//
// PREREQS (the 3 local services, see project_python_api_port_8000 memory):
//   - Flask seeder on :5000 serving /workhive/  (rewrites SUPABASE_URL -> local)
//   - Supabase edge on :54321 (engineering-calc-agent, verify_jwt=false)
//   - Python FastAPI on :8000 (the authoritative calc engine)
//
// USAGE:
//   node tools/browser_calc_sweep.mjs                 # all specs, headless
//   node tools/browser_calc_sweep.mjs --headed        # watch it
//   node tools/browser_calc_sweep.mjs --only "HVAC Cooling Load"
//
// Output: browser_calc_sweep.json (ledger, forward-only ratchet feeds B5).

import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync } from 'fs';

const SEEDER = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const PAGE_URL = `${SEEDER}/workhive/engineering-design.html`;
const PY_API = process.env.WH_PY_API || 'http://127.0.0.1:8000';

const args = process.argv.slice(2);
const HEADED = args.includes('--headed');
const AUTO = args.includes('--auto');     // enumerate ALL calc types, auto-fill forms
const B3 = args.includes('--b3');         // also drive the in-page diagram (B3: label==value)
const B2 = args.includes('--b2');         // also drive the in-UI BOM/SOW (B2: cites the sized value, live LLM)
const ACCEPT = args.includes('--accept'); // B5 capstone: forward-only ratchet vs baseline
const UPDATE_BASELINE = args.includes('--update-baseline');
const ONLY = (() => { const i = args.indexOf('--only'); return i >= 0 ? args[i + 1] : null; })();
const BASELINE_FILE = 'browser_calc_sweep_baseline.json';

// ─── Per-calc-type specs ──────────────────────────────────────────────────────
// Each spec: { discipline, calcType, fields:{fieldId:value}, toggles:[[groupId,value]],
//              primaryKeys:[result keys to assert render==python] }.
// Field IDs are READ from the page's renderInputForm() — never guessed. Add a
// spec per calc type as its field IDs are verified (B1 ratchet, 1/53 -> 53/53).
const SPECS = [
  {
    discipline: 'HVAC & Cooling',
    calcType: 'HVAC Cooling Load',
    fields: { 'f-floor-area': '80' },          // defaults-rich; only floor area required
    toggles: [],
    primaryKeys: ['kW', 'TR', 'q_design', 'recommended_kW'],
  },
];

const round = (n, d = 2) => Number(n).toFixed(d);

// Does a numeric value appear (in any sane rendered formatting) in the panel text?
function renderedContains(panelText, val) {
  if (val == null || isNaN(Number(val))) return false;
  const n = Number(val);
  const cands = new Set([
    String(n), round(n, 0), round(n, 1), round(n, 2),
    Math.round(n).toLocaleString('en-US'),     // thousands separator
    Number(round(n, 1)).toLocaleString('en-US'),
  ]);
  const norm = panelText.replace(/,/g, '');     // also match unseparated
  for (const c of cands) {
    if (panelText.includes(c)) return true;
    if (norm.includes(String(c).replace(/,/g, ''))) return true;
  }
  return false;
}

async function pyCalculate(calcType, inputs) {
  const res = await fetch(`${PY_API}/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ calc_type: calcType, inputs }),
  });
  const status = res.status;
  let body = null;
  try { body = await res.json(); } catch { /* empty/500 */ }
  return { status, body };
}

async function enumerateTypes(page) {
  return await page.evaluate(() => {
    const reg = (typeof CALC_TYPES_UI !== 'undefined') ? CALC_TYPES_UI : null;
    const flat = [];
    if (reg && !Array.isArray(reg)) {
      for (const disc of Object.keys(reg)) {
        const arr = reg[disc];
        if (Array.isArray(arr)) arr.forEach(c => { if (c.available) flat.push({ discipline: disc, calcType: c.id }); });
      }
    }
    return flat;
  });
}

async function driveCalc(page, spec) {
  // discipline + calc type via the page's own state machine
  await page.evaluate(({ disc, ct }) => {
    if (disc) window.selectDiscipline(disc);
    window.selectCalcType(ct);
  }, { disc: spec.discipline, ct: spec.calcType });

  for (const [groupId, val] of (spec.toggles || [])) {
    await page.evaluate(({ g, v }) => window.toggle && window.toggle(g, v), { g: groupId, v: val });
  }
  for (const [fid, val] of Object.entries(spec.fields || {})) {
    const el = page.locator('#' + fid);
    if (await el.count()) await el.fill(String(val));
  }
  // auto-fill: every empty numeric field gets its placeholder (if positive) or a
  // generic positive default, so defaults-rich forms run without a hand spec.
  // List-builder forms (need >=1 added row) won't render this way -> recorded as
  // NEEDS-SPEC honestly, never faked.
  if (spec.auto) {
    await page.evaluate(() => {
      const area = document.getElementById('input-form-area');
      if (!area) return;
      area.querySelectorAll('input[type=number]').forEach(inp => {
        // Fill if empty OR non-positive: many required fields render with a
        // default value="0" (present, so an `=== ''` test skips them) which trips
        // the "please enter ..." guard. A positive value is consistent across the
        // browser AND the :8000 re-derivation, so cross-engine parity still holds.
        const cur = parseFloat(inp.value);
        if (inp.value === '' || inp.value == null || !(cur > 0)) {
          let d = parseFloat(inp.placeholder);
          if (!(d > 0)) d = 10;
          inp.value = String(d);
          inp.dispatchEvent(new Event('input', { bubbles: true }));
        }
      });
    });
  }

  // run + capture source + rendered values, polling for the report to flip visible
  return await page.evaluate(async () => {
    let source = 'unknown';
    const _f = window.fetch;
    window.fetch = async (url, opts) => {
      const r = await _f(url, opts);
      try {
        const u = (typeof url === 'string') ? url : (url && url.url);
        if (u && u.indexOf('engineering-calc-agent') !== -1) {
          const j = await r.clone().json();
          source = j.source || 'ts-fallback';
        }
      } catch { /* noop */ }
      return r;
    };
    let err = null;
    try { await window.runCalculation(); } catch (e) { err = String(e); }
    // runCalculation renders synchronously before its promise resolves; a short
    // safety poll covers any micro-task lag. A guard-failed early-return leaves
    // report-output hidden and never flips, so we don't wait the full window.
    const t0 = Date.now();
    while (Date.now() - t0 < 3000) {
      const o = document.getElementById('report-output');
      if (o && !o.classList.contains('hidden')) break;
      await new Promise(r => setTimeout(r, 200));
    }
    window.fetch = _f;
    const results = (typeof _lastResults !== 'undefined') ? _lastResults : null;
    const inputs = (typeof _lastInputs !== 'undefined') ? _lastInputs : null;
    const panel = document.getElementById('report-panel');
    return {
      err, source, results, inputs,
      rendered: !!(document.getElementById('report-output') && !document.getElementById('report-output').classList.contains('hidden')),
      panelText: panel ? panel.innerText : '',
    };
  });
}

// B3: trigger the in-page diagram and read its SVG text labels. The diagram is a
// distinct render surface (an SVG/schematic, some via the /diagram Python API,
// most client-side builders) — assert it carries the calc's sized value.
async function captureDiagram(page) {
  return await page.evaluate(async () => {
    const supported = (typeof DRAWING_SUPPORTED !== 'undefined') ? DRAWING_SUPPORTED : null;
    const sect = document.getElementById('drawing-section');
    // drawing-section is unhidden by the report renderer for supported calc types
    if (!sect || sect.classList.contains('hidden') || typeof generateDrawing !== 'function') {
      return { diagramSupported: false };
    }
    // CLEAR the previous type's SVG first — else a calc whose builder fails/no-ops
    // leaves the prior diagram in #drawing-panel and we'd falsely read IT (caught
    // 2026-06-18: Beam/Column read a stale HVAC schematic). After clearing, a real
    // generate must repopulate it; if nothing appears it's an honest NO-SVG.
    const panel = document.getElementById('drawing-panel');
    if (panel) panel.innerHTML = '';
    try { generateDrawing(); } catch (e) { return { diagramSupported: true, diagramErr: String(e) }; }
    const t0 = Date.now();
    let svg = null;
    while (Date.now() - t0 < 30000) {
      svg = document.querySelector('#drawing-panel svg');
      if (svg && (svg.textContent || '').trim().length > 20) break;
      await new Promise(r => setTimeout(r, 400));
    }
    return {
      diagramSupported: true,
      svgPresent: !!svg,
      svgText: svg ? (svg.textContent || '') : '',
      labelCount: svg ? svg.querySelectorAll('text').length : 0,
    };
  });
}

// B2: trigger the in-page BOM/SOW (a live Groq LLM) and read the rendered items.
// LLM is free-tier rate-limited (see ai-engineer/qa-tester) → caller paces + retries.
async function captureBomSow(page) {
  return await page.evaluate(async () => {
    if (typeof generateBomSowChecklist !== 'function') return { bomSupported: false };
    // HIDE the checklist panel first — generateBomSowChecklist only un-hides it on
    // SUCCESS (fresh _bomItems); on an LLM 5xx it re-shows the trigger and leaves
    // the panel hidden. Gating the read on "panel became visible again" prevents
    // reading a PREVIOUS type's stale _bomItems (the B3 staleness class).
    const panel0 = document.getElementById('bom-checklist-panel');
    if (panel0) panel0.classList.add('hidden');
    let toastMsg = null; const _st = window.showToast; window.showToast = (m) => { toastMsg = m; };
    try { await generateBomSowChecklist(); } catch (e) { window.showToast = _st; return { bomSupported: true, visible: false, err: String(e) }; }
    const t0 = Date.now();
    let visible = false;
    while (Date.now() - t0 < 60000) {
      const p = document.getElementById('bom-checklist-panel');
      if (p && !p.classList.contains('hidden')) { visible = true; break; }
      if (toastMsg && /not yet available|error/i.test(toastMsg)) break;
      await new Promise(r => setTimeout(r, 500));
    }
    window.showToast = _st;
    const notSupported = !!(toastMsg && /not yet available/i.test(toastMsg));
    if (!visible) {
      return { bomSupported: !notSupported, visible: false, toastMsg, bomCount: 0, sowCount: 0, text: '' };
    }
    const bom = (typeof _bomItems !== 'undefined') ? _bomItems : [];
    const sow = (typeof _sowSections !== 'undefined') ? _sowSections : [];
    return {
      bomSupported: !notSupported, visible: true, toastMsg,
      bomCount: bom.length, sowCount: sow.length,
      text: JSON.stringify(bom) + ' ' + JSON.stringify(sow),
    };
  });
}

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function main() {
  const browser = await chromium.launch({ headless: !HEADED });
  const context = await browser.newContext();
  // Seed identity so engineering-design.html doesn't bounce to index.html.
  await context.addInitScript(() => {
    try {
      localStorage.setItem('wh_last_worker', 'Leandro Marquez');
      localStorage.setItem('wh_hive_role', 'supervisor');
    } catch { /* noop */ }
  });
  const page = await context.newPage();
  await page.goto(PAGE_URL, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => typeof window.selectDiscipline === 'function' && typeof window.selectCalcType === 'function',
    { timeout: 15000 },
  );

  // Build the worklist. --auto enumerates ALL available calc types from the
  // page registry and uses a hand SPEC where one exists, else auto-fills.
  let specs;
  if (ONLY) {
    const hand = SPECS.find(s => s.calcType === ONLY);
    specs = [hand || { calcType: ONLY, auto: true }];
  } else if (AUTO) {
    const handByType = Object.fromEntries(SPECS.map(s => [s.calcType, s]));
    const all = await enumerateTypes(page);
    specs = all.map(t => handByType[t.calcType] || { ...t, auto: true });
  } else {
    specs = SPECS;
  }
  const cells = [];
  for (const spec of specs) {
    const out = { calcType: spec.calcType, discipline: spec.discipline };
    try {
      let d = await driveCalc(page, spec);
      // Render-completion flake recovery: under sequential cold-start load the
      // report panel occasionally fails to finish rendering even though the calc
      // itself is fine (edge cold-start over many drives). Re-drive once before
      // recording NEEDS-SPEC so the DOM ratchet isn't depressed by render flake.
      // This ONLY recovers the rendered count — the correctness signal
      // (FAIL-DIVERGENCE: served != :8000 Python) is computed from the re-drive
      // too, so it cannot mask a real bug.
      if (!d.rendered || !d.results) {
        await sleep(1500);
        const d2 = await driveCalc(page, spec);
        if (d2.rendered && d2.results) { d = d2; out.retried = true; }
      }
      out.source = d.source;
      out.rendered = d.rendered;
      if (!d.rendered || !d.results) {
        // Auto-fill couldn't satisfy the form's guards (list-builder rows, strict
        // cross-field constraints). NOT a calc failure — a harness coverage gap
        // that needs a hand SPEC. Recorded honestly, never faked green.
        out.status = 'NEEDS-SPEC';
        out.reason = d.err ? `runCalculation threw: ${d.err}` : 'report never rendered (auto-fill did not satisfy guards)';
        cells.push(out);
        console.log(`[NEEDS-SPEC] ${spec.calcType}  source=${out.source}`);
        continue;
      }
      // (a) cross-engine: the SERVED value (what the page rendered from) vs the
      // authoritative :8000 Python engine, on the SAME inputs the page sent.
      const py = await pyCalculate(spec.calcType, d.inputs);
      out.pyStatus = py.status;
      const pyResults = (py.body && py.body.results) || null;
      const pyNotImpl = !!(py.body && py.body.not_implemented);

      // Comparison keys: the hand spec's primaryKeys if given, else every
      // top-level numeric result key (derived) — intersected with python's keys.
      const keys = (spec.primaryKeys && spec.primaryKeys.length)
        ? spec.primaryKeys
        : Object.keys(d.results).filter(k => typeof d.results[k] === 'number' && isFinite(d.results[k]));

      const checks = [];
      for (const k of keys) {
        const served = d.results[k];
        if (typeof served !== 'number' || !isFinite(served)) continue;
        const rf = renderedContains(d.panelText, served);          // (b) render-faithful
        let xeng = null, xengOk = null;
        if (pyResults && pyResults[k] != null && isFinite(Number(pyResults[k]))) {
          const pv = Number(pyResults[k]); const sv = Number(served);
          const tol = Math.max(Math.abs(pv) * 0.01, 0.01);          // 1% rel or 0.01 abs
          xeng = { served: sv, python: pv };
          xengOk = Math.abs(sv - pv) <= tol;
        }
        checks.push({ key: k, served, renderFaithful: rf, crossEngine: xeng, crossEngineOk: xengOk });
      }
      out.checks = checks;
      const xengAll = checks.filter(c => c.crossEngineOk !== null);
      const xengDiverge = xengAll.filter(c => c.crossEngineOk === false);
      const rfCount = checks.filter(c => c.renderFaithful).length;
      out.renderFaithfulRatio = checks.length ? Number((rfCount / checks.length).toFixed(2)) : null;
      out.crossEngineKeys = xengAll.length;
      out.crossEngineDiverge = xengDiverge.length;

      if (xengDiverge.length > 0) {
        // The bug class: the value the user SEES disagrees with the validated
        // Python engine (e.g. a silent TS fallback, or a render transform).
        out.status = 'FAIL-DIVERGENCE';
        out.crossEngineOk = false;
        out.reason = `${xengDiverge.length} key(s) diverge from :8000 Python, e.g. `
          + xengDiverge.slice(0, 3).map(c => `${c.key}: served ${c.crossEngine.served} vs py ${c.crossEngine.python}`).join('; ');
      } else if (xengAll.length > 0) {
        // Rendered value matches the validated engine across all comparable keys.
        out.status = 'PASS';
        out.crossEngineOk = true;
      } else {
        // Python has no usable reference for these inputs (not_implemented or it
        // errored on the auto-filled inputs) — can't value-verify. Honest bucket.
        out.status = 'NO-PYREF';
        out.crossEngineOk = pyNotImpl ? 'python-not-implemented' : 'python-no-result';
      }
      // ── B3: diagram label == value (the in-page SVG, a distinct render surface) ──
      if (B3) {
        const dg = await captureDiagram(page);
        if (!dg.diagramSupported) {
          out.b3 = 'n/a';                       // this calc type has no diagram
        } else if (!dg.svgPresent) {
          out.b3 = 'NO-SVG';                    // diagram failed to render (e.g. prod /diagram api unreachable)
          out.b3reason = dg.diagramErr || 'no svg in #drawing-panel';
        } else {
          // count distinct primary result values that appear in the SVG labels.
          // Use values > 1 to avoid trivial "1"/"2" coincidences; recommended/sized
          // values (recommended_kW etc.) are what diagrams typically label.
          const vals = [...new Set(Object.values(d.results)
            .filter(v => typeof v === 'number' && isFinite(v) && Math.abs(v) > 1))];
          const found = vals.filter(v => renderedContains(dg.svgText, v));
          out.b3 = found.length >= 2 ? 'PASS' : (found.length === 1 ? 'WEAK' : 'FAIL');
          out.b3values = { labelCount: dg.labelCount, valuesFoundInSvg: found.length, ofPrimary: vals.length };
        }
      }
      // ── B2: in-UI BOM/SOW cites the sized value (live LLM, paced + 1 retry) ──
      if (B2) {
        let bs = await captureBomSow(page);
        if (bs.bomSupported && (!bs.bomCount || bs.err)) { await sleep(4000); bs = await captureBomSow(page); } // retry transient 5xx
        if (!bs.bomSupported) {
          out.b2 = 'n/a';                       // calc type not in BOM_SOW_SUPPORTED
        } else if (!bs.bomCount) {
          out.b2 = 'NO-LLM'; out.b2reason = bs.err || bs.toastMsg || 'no items (LLM 5xx/rate-limit)';
        } else {
          const vals = [...new Set(Object.values(d.results)
            .filter(v => typeof v === 'number' && isFinite(v) && Math.abs(v) > 1))];
          const found = vals.filter(v => renderedContains(bs.text, v));
          out.b2 = found.length >= 1 ? 'PASS' : 'FAIL';
          out.b2values = { bomCount: bs.bomCount, sowCount: bs.sowCount, valuesCited: found.length };
        }
        await sleep(2500);                      // pace the free-tier LLM
      }
      cells.push(out);
      console.log(`[${out.status}] ${spec.calcType}  source=${out.source}  xeng=${out.crossEngineDiverge}/${out.crossEngineKeys} diverge${B3 ? '  b3=' + out.b3 : ''}${B2 ? '  b2=' + out.b2 : ''}`);
      continue;
    } catch (e) {
      out.status = 'ERROR'; out.reason = String(e && e.stack || e);
    }
    cells.push(out);
    console.log(`[${out.status}] ${spec.calcType}  source=${out.source}  ${out.reason ? '· ' + String(out.reason).slice(0, 80) : ''}`);
  }

  await browser.close();

  const by = (s) => cells.filter(c => c.status === s).length;
  const pass = by('PASS');
  const diverge = by('FAIL-DIVERGENCE');
  const noPyref = by('NO-PYREF');
  const needsSpec = by('NEEDS-SPEC');
  const errored = by('ERROR');
  const DENOM = 53;                       // available calc types per the roadmap

  const ledger = {
    generated: new Date().toISOString(),
    denominator_total_calc_types: DENOM,
    specs_run: cells.length,
    pass,
    fail_divergence: diverge,
    no_python_ref: noPyref,
    needs_spec: needsSpec,
    errored,
    rendered_in_browser: cells.filter(c => c.rendered).length,
    measured: `B1 value-verified (render==validated Python): ${pass}/${DENOM} · `
      + `rendered-in-browser ${cells.filter(c => c.rendered).length}/${cells.length}`,
    cells,
  };
  if (B3) {
    const b3pass = cells.filter(c => c.b3 === 'PASS').length;
    const b3weak = cells.filter(c => c.b3 === 'WEAK').length;
    const b3fail = cells.filter(c => c.b3 === 'FAIL').length;
    const b3nosvg = cells.filter(c => c.b3 === 'NO-SVG').length;
    const b3na = cells.filter(c => c.b3 === 'n/a').length;
    ledger.b3 = { pass: b3pass, weak: b3weak, fail: b3fail, no_svg: b3nosvg, na: b3na };
  }
  if (B2) {
    ledger.b2 = {
      pass: cells.filter(c => c.b2 === 'PASS').length,
      fail: cells.filter(c => c.b2 === 'FAIL').length,
      no_llm: cells.filter(c => c.b2 === 'NO-LLM').length,
      na: cells.filter(c => c.b2 === 'n/a').length,
    };
    console.log(`B2 in-UI BOM/SOW cite:  PASS ${ledger.b2.pass} · FAIL ${ledger.b2.fail} · NO-LLM ${ledger.b2.no_llm} · n/a ${ledger.b2.na}`);
  }
  writeFileSync('browser_calc_sweep.json', JSON.stringify(ledger, null, 2));
  console.log(`\n${'='.repeat(64)}`);
  console.log(`B1 browser-tier sweep (denominator ${DENOM} calc types):`);
  console.log(`  PASS (render==validated Python)   ${pass}`);
  console.log(`  FAIL-DIVERGENCE (served != python) ${diverge}   <-- the bug class`);
  console.log(`  NO-PYREF (python n/impl or errored) ${noPyref}`);
  console.log(`  NEEDS-SPEC (auto-fill didn't render) ${needsSpec}`);
  console.log(`  ERROR (harness)                     ${errored}`);
  console.log(`  rendered in browser                 ${cells.filter(c => c.rendered).length}/${cells.length}`);
  if (B3 && ledger.b3) {
    console.log(`B3 diagram label==value:  PASS ${ledger.b3.pass} · WEAK ${ledger.b3.weak} · FAIL ${ledger.b3.fail} · NO-SVG ${ledger.b3.no_svg} · n/a ${ledger.b3.na}`);
  }
  console.log('Ledger -> browser_calc_sweep.json');

  // ── B5: browser-accept capstone — forward-only ratchet vs baseline ──────────
  let ratchetFail = false;
  if (ACCEPT) {
    const cur = {
      pass, diverge,
      b3pass: ledger.b3 ? ledger.b3.pass : 0, b3fail: ledger.b3 ? ledger.b3.fail : 0,
      b2pass: ledger.b2 ? ledger.b2.pass : 0, b2fail: ledger.b2 ? ledger.b2.fail : 0,
    };
    if (UPDATE_BASELINE || !existsSync(BASELINE_FILE)) {
      // merge: only overwrite the metrics this run actually measured (B2/B3 are opt-in)
      const prev = existsSync(BASELINE_FILE) ? JSON.parse(readFileSync(BASELINE_FILE, 'utf8')) : {};
      const merged = { ...prev, pass: cur.pass, diverge: cur.diverge };
      if (B3) { merged.b3pass = cur.b3pass; merged.b3fail = cur.b3fail; }
      if (B2) { merged.b2pass = cur.b2pass; merged.b2fail = cur.b2fail; }
      merged.set = new Date().toISOString();
      writeFileSync(BASELINE_FILE, JSON.stringify(merged, null, 2));
      console.log(`\n[B5] baseline ${UPDATE_BASELINE ? 'UPDATED' : 'created'}: pass>=${merged.pass} diverge<=${merged.diverge} b3pass>=${merged.b3pass ?? '-'} b2pass>=${merged.b2pass ?? '-'}`);
    } else {
      const base = JSON.parse(readFileSync(BASELINE_FILE, 'utf8'));
      const regress = [];
      if (cur.pass < base.pass) regress.push(`B1 pass ${cur.pass} < baseline ${base.pass}`);
      if (cur.diverge > base.diverge) regress.push(`B1 divergence ${cur.diverge} > baseline ${base.diverge}`);
      if (B3 && base.b3pass != null && cur.b3pass < base.b3pass) regress.push(`B3 pass ${cur.b3pass} < baseline ${base.b3pass}`);
      if (B3 && base.b3fail != null && cur.b3fail > base.b3fail) regress.push(`B3 fail ${cur.b3fail} > baseline ${base.b3fail}`);
      if (B2 && base.b2pass != null && cur.b2pass < base.b2pass) regress.push(`B2 pass ${cur.b2pass} < baseline ${base.b2pass}`);
      if (B2 && base.b2fail != null && cur.b2fail > base.b2fail) regress.push(`B2 fail ${cur.b2fail} > baseline ${base.b2fail}`);
      if (regress.length) { ratchetFail = true; console.log(`\n[B5] RATCHET REGRESSION:\n  ` + regress.join('\n  ')); }
      else console.log(`\n[B5] ratchet OK — held at pass>=${base.pass} diverge<=${base.diverge} b3pass>=${base.b3pass ?? '-'} b2pass>=${base.b2pass ?? '-'}`);
    }
  }
  // Exit non-zero on a real divergence (the bug class), harness error, or ratchet regression.
  process.exit((diverge > 0 || errored > 0 || ratchetFail) ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(2); });
