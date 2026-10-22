/* kpi-calc.js - the OEE calculator and the MTBF & MTTR calculator, worked out on the page (ENH-P, 2026-10-23).
 *
 * tools/oee-calculator and tools/mtbf-calculator sent their reader to analytics.html, which works these figures out
 * from the person's OWN log - and a stranger who searched for "OEE calculator" has no log yet: the page offered a
 * worked example and a tool they could not use. These are two short formulas, so they run here, on the device, and
 * nothing entered leaves the page. Built the way solar-planner.js (ENH-S) is: the arithmetic is a pure function that
 * tools/test_kpi_calc.mjs holds to the pages' own worked examples, and the person can read what to do about the
 * number, print the calculation with its inputs and its standard, save it on the device, share it by a link that
 * carries it, and keep one result as scenario A beside the next.
 *
 *   WhKpiCalc.oee(input)   input: { mode: 'records'|'percent', planned_min, down_min, ideal_s, units, good, a_pct, p_pct, q_pct }
 *   WhKpiCalc.mtbf(input)  input: { op_h, failures, repair_h }
 *   WhKpiCalc.mount(root)  draws the calculator its data-wh-kpi-calc names ("oee" or "mtbf")
 */
(function () {
  'use strict';

  function num(v, d) { var n = Number(v); return isFinite(n) ? n : d; }
  function r1(n) { return Math.round(n * 10) / 10; }
  function pc(x) { return r1(x * 100) + '%'; }
  function n0(n) { return Math.round(n).toLocaleString('en-PH'); }
  function n1(n) { return r1(n).toLocaleString('en-PH'); }

  // Nakajima's world-class levels: OEE 85% as availability 90% x performance 95% x quality 99.9%
  var WORLD = { a: 0.90, p: 0.95, q: 0.999, oee: 0.85 };

  function oee(input) {
    var i = input || {};
    var out = { mode: i.mode === 'percent' ? 'percent' : 'records', errors: [], warnings: [] };
    var A, P, Q;
    if (out.mode === 'percent') {
      A = num(i.a_pct, NaN) / 100; P = num(i.p_pct, NaN) / 100; Q = num(i.q_pct, NaN) / 100;
      [['Availability', A], ['Performance', P], ['Quality', Q]].forEach(function (f) {
        if (!(f[1] >= 0 && f[1] <= 1)) out.errors.push(f[0] + ' must be a percentage from 0 to 100.');
      });
    } else {
      var planned = num(i.planned_min, NaN), down = num(i.down_min, NaN), ideal = num(i.ideal_s, NaN);
      var units = num(i.units, NaN), good = num(i.good, NaN);
      if (!(planned > 0)) out.errors.push('Enter the planned production time.');
      if (!(down >= 0)) out.errors.push('Enter the downtime (0 if the line never stopped).');
      else if (planned > 0 && down >= planned) out.errors.push('Downtime must be less than the planned production time.');
      if (!(ideal > 0)) out.errors.push('Enter the ideal cycle time: the rated seconds per unit.');
      if (!(units > 0)) out.errors.push('Enter how many units were produced.');
      if (!(good >= 0)) out.errors.push('Enter how many of them were good.');
      else if (units > 0 && good > units) out.errors.push('Good units cannot be more than the units produced.');
      if (!out.errors.length) {
        var run = planned - down;
        A = run / planned;
        P = (ideal * units) / (run * 60);
        Q = good / units;
        out.run_min = run;
        out.ideal_units = Math.floor((run * 60) / ideal);
        out.rejects = units - good;
        out.down_min = down; out.planned_min = planned; out.units = units;
        if (P > 1) out.warnings.push('The line made more units than its ideal cycle time allows (' + pc(P) + ' performance). '
          + 'The ideal cycle time is the machine\'s rated, fastest time per unit - check it before trusting this OEE.');
      }
    }
    if (out.errors.length) return out;
    out.a = A; out.p = P; out.q = Q; out.oee = A * P * Q;
    if (out.oee >= WORLD.oee) {
      out.advice = 'At or above the 85% world-class benchmark (Nakajima). Hold it: keep logging every stop, so a slide shows early.';
      return out;
    }
    // the biggest loss is the factor furthest below its world-class level
    var f = [['a', A], ['p', P], ['q', Q]].sort(function (x, y) { return x[1] / WORLD[x[0]] - y[1] / WORLD[y[0]]; })[0];
    var lifted = (f[0] === 'a' ? WORLD.a : A) * (f[0] === 'p' ? WORLD.p : P) * (f[0] === 'q' ? WORLD.q : Q);
    var rec = out.mode === 'records';
    var why = {
      a: 'Availability is the biggest loss' + (rec ? ': ' + n0(out.down_min) + ' of ' + n0(out.planned_min) + ' planned minutes went to stops' : '')
        + '. Log every stop with its cause for two weeks, then fix the two that cost the most minutes - breakdowns and changeovers are usually most of it.',
      p: 'Performance is the biggest loss' + (rec ? ': the line made ' + n0(out.units) + ' units where its rated speed allows ' + n0(out.ideal_units) : '')
        + '. Look for short stops and slow running, and check that the ideal cycle time is the machine\'s rated speed.',
      q: 'Quality is the biggest loss' + (rec ? ': ' + n0(out.rejects) + ' of ' + n0(out.units) + ' units were rejects' : '')
        + '. Start with the most common defect, and count start-up rejects apart from steady running.'
    }[f[0]];
    out.loss = f[0];
    out.lifted = lifted;
    out.advice = why + ' Raising it to the world-class ' + pc(WORLD[f[0]]) + ' would lift OEE to ' + pc(lifted) + '.';
    return out;
  }

  function mtbf(input) {
    var i = input || {};
    var out = { errors: [], warnings: [] };
    var op = num(i.op_h, NaN), f = num(i.failures, NaN), rep = num(i.repair_h, NaN);
    if (!(op > 0)) out.errors.push('Enter the operating hours.');
    if (!(f >= 0) || Math.floor(f) !== f) out.errors.push('Enter the number of failures as a whole number (0 if there were none).');
    if (!(rep >= 0)) out.errors.push('Enter the total repair hours (0 if there were none).');
    if (out.errors.length) return out;
    out.op_h = op; out.failures = f; out.repair_h = rep;
    if (f === 0) {
      out.noFailures = true;
      out.advice = 'No failures in this period, so MTBF is at least ' + n0(op) + ' hours and MTTR cannot be worked out yet. '
        + 'Keep logging: the first failure makes both computable.';
      return out;
    }
    var M = op / f, R = rep / f;
    out.mtbf = M; out.mttr = R; out.avail = M / (M + R);
    if (R <= 0) {
      out.advice = 'No repair time is recorded, so availability reads 100%. Record the repair hours with each failure, or this figure flatters the asset.';
    } else if (R > 1) {
      // cutting each repair by an hour moves availability as far as running M/(R-1) hours longer between failures
      out.hourWorth = M / (R - 1);
      out.advice = 'Each failure costs ' + n1(R) + ' hours of repair, about every ' + n0(M) + ' hours of running. Cutting each repair by an hour '
        + 'gains as much availability as ' + n0(out.hourWorth) + ' more hours between failures: start with spares on hand and a written repair '
        + 'procedure. To stop the failures themselves, find the cause of the one that repeats and put the fix into the PM plan.';
    } else {
      out.advice = 'Repairs are already short (' + n1(R) + ' hours each). The gain now is in failing less: find the cause of the failure that '
        + 'repeats and put the fix into the PM plan.';
    }
    return out;
  }

  // ── state: what a calculation is, as saved and shared ─────────────────────────────────────────────
  function encode(st) {
    try { return btoa(unescape(encodeURIComponent(JSON.stringify(st)))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); }
    catch (_) { return ''; }   // empty-catch-allow: nothing to share; the caller says so
  }
  function decode(t) {
    try {
      var b = String(t).replace(/-/g, '+').replace(/_/g, '/');
      while (b.length % 4) b += '=';
      var o = JSON.parse(decodeURIComponent(escape(atob(b))));
      return o && o.v === 1 ? o : null;
    } catch (_) { return null; }   // empty-catch-allow: a damaged link opens the worked example instead
  }

  var DEF = {
    // the pages' own worked examples, entered: OEE 90% x 95% x 98%; MTBF 4,000 h, 5 failures, 40 h of repair
    oee: { v: 1, k: 'oee', mode: 'records', planned_min: 480, down_min: 48, ideal_s: 1.2, units: 20520, good: 20110, a_pct: 90, p_pct: 95, q_pct: 98 },
    mtbf: { v: 1, k: 'mtbf', op_h: 4000, failures: 5, repair_h: 40 }
  };
  var META = {
    oee: { title: 'OEE calculation', standard: 'Nakajima TPM | ISO 22400-2',
      method: 'OEE = Availability x Performance x Quality. Availability = run time / planned production time; Performance = (ideal cycle time x units) / run time; Quality = good units / units.' },
    mtbf: { title: 'MTBF & MTTR calculation', standard: 'ISO 14224 | IEC 60050-192 | SMRP',
      method: 'MTBF = operating hours / failures. MTTR = repair hours / repairs (one repair per failure). Availability = MTBF / (MTBF + MTTR).' }
  };
  var FIELDS = {
    oee: {
      records: [['planned_min', 'Planned production time (minutes)', 1], ['down_min', 'Downtime (minutes)', 0], ['ideal_s', 'Ideal cycle time (seconds per unit)', 0.01],
        ['units', 'Units produced', 1], ['good', 'Good units', 0]],
      percent: [['a_pct', 'Availability (%)', 0], ['p_pct', 'Performance (%)', 0], ['q_pct', 'Quality (%)', 0]]
    },
    mtbf: [['op_h', 'Operating hours', 1], ['failures', 'Number of failures', 0], ['repair_h', 'Total repair hours', 0]]
  };

  var CSS = '' +
    '.wh-kc{--kc-line:rgba(255,255,255,0.10);--kc-muted:rgba(244,246,250,0.80);color:var(--wh-cloud,#F4F6FA);container-type:inline-size}' +
    '.wh-kc h3{margin:1.5rem 0 0.5rem;font-size:1.125rem;font-weight:700;line-height:1.35}' +
    '.wh-kc h3:first-child{margin-top:0.25rem}' +
    '.wh-kc p{margin:0 0 0.75rem}' +
    '.wh-kc .kc-help{font-size:0.875rem;color:var(--kc-muted);line-height:1.55}' +
    '.wh-kc label{display:block;font-size:0.75rem;font-weight:600;color:var(--kc-muted);margin:0 0 4px}' +
    '.wh-kc input[type=number]{width:100%;box-sizing:border-box;min-height:44px;padding:8px 10px;border-radius:8px;border:1px solid rgba(255,255,255,0.18);' +
      'background:var(--wh-navy-mid,#1F2E45);color:var(--wh-cloud,#F4F6FA);font:inherit;font-size:1rem;font-variant-numeric:tabular-nums}' +
    '.wh-kc input:focus-visible,.wh-kc button:focus-visible{outline:2px solid var(--wh-orange,#F7A21B);outline-offset:2px}' +
    '.wh-kc .kc-grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr));align-items:end}' +
    '.wh-kc .kc-mode{display:flex;flex-wrap:wrap;gap:8px 20px;margin:0 0 12px;border:0;padding:0}' +
    '.wh-kc .kc-mode legend{font-size:0.75rem;font-weight:600;color:var(--kc-muted);margin:0 0 6px;padding:0}' +
    '.wh-kc .kc-mode label{display:flex;align-items:center;gap:8px;min-height:44px;margin:0;font-size:0.875rem;color:var(--wh-cloud,#F4F6FA)}' +
    '.wh-kc .kc-mode input{width:20px;height:20px;accent-color:var(--wh-orange,#F7A21B)}' +
    '.wh-kc button{min-height:44px;padding:0 16px;border-radius:8px;font:inherit;font-size:0.875rem;font-weight:600;cursor:pointer;' +
      'border:1px solid rgba(255,255,255,0.22);background:transparent;color:var(--wh-cloud,#F4F6FA)}' +
    '.wh-kc button:hover{border-color:rgba(255,255,255,0.40)}' +
    '.wh-kc button.kc-primary{background:var(--wh-orange,#F7A21B);border-color:var(--wh-orange,#F7A21B);color:var(--wh-navy,#162032)}' +
    '.wh-kc button.kc-primary:hover{background:var(--wh-orange-light,#FDB94A);border-color:var(--wh-orange-light,#FDB94A)}' +
    '.wh-kc .kc-result{margin:0;padding:0;list-style:none;border-top:1px solid var(--kc-line)}' +
    '.wh-kc .kc-result>li{list-style:none;margin:0;padding:12px 0;border-bottom:1px solid var(--kc-line)}' +
    '.wh-kc .kc-q{font-weight:700;font-size:0.95rem;margin:0 0 4px}' +
    '.wh-kc .kc-a{font-size:1.125rem;font-weight:700;font-variant-numeric:tabular-nums;color:var(--wh-orange-light,#FDB94A);margin:0 0 4px}' +
    '.wh-kc .kc-how{font-size:0.875rem;color:var(--kc-muted);line-height:1.55;font-variant-numeric:tabular-nums;margin:0}' +
    '.wh-kc .kc-advice{font-size:0.95rem;line-height:1.55;margin:12px 0 0}' +
    '.wh-kc .kc-warn{color:var(--wh-red-text,#FDC9C9);font-size:0.875rem;line-height:1.55;margin:8px 0 0}' +
    '.wh-kc .kc-actions{display:flex;flex-wrap:wrap;gap:8px;margin:1rem 0 0.25rem}' +
    '.wh-kc .kc-said{min-height:1.5em;font-size:0.875rem;color:var(--kc-muted);margin:0.25rem 0 0}' +
    '.wh-kc .kc-copy{margin-top:8px}' +
    '.wh-kc .kc-compare{margin:12px 0 0;padding:12px 14px;border:1px solid rgba(41,182,217,0.28);border-radius:12px;background:rgba(41,182,217,0.06)}' +
    '.wh-kc .kc-compare h4{margin:0 0 6px;font-size:0.95rem;font-weight:700}' +
    '.wh-kc table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:0.875rem}' +
    '.wh-kc th,.wh-kc td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--kc-line);vertical-align:top}' +
    '.wh-kc td.kc-diff{font-weight:700;color:#fff}' +
    '.wh-kc-sheet{display:none}' +
    '@media print{body.wh-kc-printing>*{display:none !important}' +
      'body.wh-kc-printing{background:#fff !important}' +
      'body.wh-kc-printing>.wh-kc-sheet{display:block !important;position:static !important;color:#000;background:#fff;font:11pt/1.45 Poppins,Arial,sans-serif}' +
      'body.wh-kc-printing>.wh-kc-sheet,body.wh-kc-printing>.wh-kc-sheet *{visibility:visible !important}' +
      '.wh-kc-sheet h2{font-size:16pt;margin:0 0 6pt}.wh-kc-sheet h4{font-size:12pt;margin:12pt 0 4pt}' +
      '.wh-kc-sheet table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}' +
      '.wh-kc-sheet th,.wh-kc-sheet td{text-align:left;border-bottom:1px solid #999;padding:3pt 5pt;vertical-align:top}' +
      '.wh-kc-sheet p{margin:0 0 6pt}}';

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === 'text') n.textContent = attrs[k];
      else if (k === 'class') n.className = attrs[k];
      else if (k.slice(0, 2) === 'on') n.addEventListener(k.slice(2), attrs[k]);
      else n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }

  // the figures a result shows, in order: [label, value as said, plain number for comparing]
  function figures(k, r) {
    if (k === 'oee') return r.errors.length ? [] : [['OEE', pc(r.oee), r.oee], ['Availability', pc(r.a), r.a], ['Performance', pc(r.p), r.p], ['Quality', pc(r.q), r.q]];
    if (r.errors.length || r.noFailures) return [];
    return [['MTBF', n1(r.mtbf) + ' h', r.mtbf], ['MTTR', n1(r.mttr) + ' h', r.mttr], ['Availability', pc(r.avail), r.avail]];
  }

  var uid = 0;
  function mount(root) {
    if (!root) return null;
    var k = root.getAttribute('data-wh-kpi-calc') === 'mtbf' ? 'mtbf' : 'oee';
    if (!document.getElementById('wh-kc-css')) {
      var st = document.createElement('style'); st.id = 'wh-kc-css'; st.textContent = CSS;
      (document.head || document.documentElement).appendChild(st);
    }
    var id = 'kc' + (++uid);
    var STORE = 'wh_kpi_' + k + '_v1';
    var state = JSON.parse(JSON.stringify(DEF[k]));
    var fromLink = /(?:^|[#&])kpi=([^&]+)/.exec(location.hash || '');
    var loaded = fromLink ? decode(fromLink[1]) : null, savedFrom = loaded && loaded.k === k ? 'link' : null;
    if (!savedFrom) { loaded = null; try { loaded = decode(localStorage.getItem(STORE) || ''); if (loaded && loaded.k === k) savedFrom = 'device'; else loaded = null; } catch (_) { loaded = null; } }   // empty-catch-allow: storage blocked; the worked example opens
    if (loaded) for (var key in state) if (loaded[key] !== undefined) state[key] = loaded[key];
    var keptA = null;

    root.classList.add('wh-kc');
    root.innerHTML = '';
    var said = el('p', { class: 'kc-said', role: 'status', 'aria-live': 'polite' });
    var say = function (t) { said.textContent = t; };
    var calc = function () { return k === 'oee' ? oee(state) : mtbf(state); };

    // inputs
    var inputs = {};
    var field = function (spec) {
      var inp = el('input', { type: 'number', id: id + '-' + spec[0], inputmode: 'decimal', min: String(spec[2]), step: 'any', value: String(state[spec[0]]) });
      inp.addEventListener('input', function () { state[spec[0]] = inp.value === '' ? '' : Number(inp.value); draw(); });
      inputs[spec[0]] = inp;
      return el('div', null, [el('label', { for: inp.id, text: spec[1] }), inp]);
    };
    var grids = {};
    var modeBox = null;
    if (k === 'oee') {
      grids.records = el('div', { class: 'kc-grid' }, FIELDS.oee.records.map(field));
      grids.percent = el('div', { class: 'kc-grid' }, FIELDS.oee.percent.map(field));
      var radio = function (val, text) {
        var r = el('input', { type: 'radio', name: id + '-mode', value: val });
        if (state.mode === val) r.checked = true;
        r.addEventListener('change', function () { if (r.checked) { state.mode = val; showMode(); draw(); } });
        return el('label', null, [r, text]);
      };
      modeBox = el('fieldset', { class: 'kc-mode' }, [el('legend', { text: 'What you have' }),
        radio('records', 'Shift records: time, stops and counts'), radio('percent', 'The three percentages')]);
    } else {
      grids.all = el('div', { class: 'kc-grid' }, FIELDS.mtbf.map(field));
    }
    function showMode() { if (k === 'oee') { grids.records.hidden = state.mode !== 'records'; grids.percent.hidden = state.mode !== 'percent'; } }

    var results = el('ul', { class: 'kc-result', 'aria-label': META[k].title });
    var advice = el('p', { class: 'kc-advice' });
    var warn = el('p', { class: 'kc-warn' });
    var compareBox = el('div', { class: 'kc-compare', hidden: '' });

    function how(label) {
      var r = calc();
      if (k === 'oee') {
        if (label === 'OEE') return pc(r.a) + ' x ' + pc(r.p) + ' x ' + pc(r.q);
        if (r.mode === 'percent') return 'As entered.';
        if (label === 'Availability') return n0(r.run_min) + ' min run of ' + n0(r.planned_min) + ' min planned';
        if (label === 'Performance') return n0(r.units) + ' units made; the rated speed allows ' + n0(r.ideal_units);
        return n0(r.units - r.rejects) + ' good of ' + n0(r.units);
      }
      if (label === 'MTBF') return n0(r.op_h) + ' h / ' + n0(r.failures) + (r.failures === 1 ? ' failure' : ' failures');
      if (label === 'MTTR') return n1(r.repair_h) + ' h of repair / ' + n0(r.failures) + (r.failures === 1 ? ' repair' : ' repairs');
      return n1(r.mtbf) + ' / (' + n1(r.mtbf) + ' + ' + n1(r.mttr) + ')';
    }

    function drawCompare(r) {
      compareBox.innerHTML = '';
      if (!keptA) { compareBox.hidden = true; return; }
      var now = figures(k, r);
      var rows = keptA.figs.map(function (f) {
        var cur = now.filter(function (x) { return x[0] === f[0]; })[0];
        var changed = !cur || cur[1] !== f[1];
        var td = el('td', changed ? { class: 'kc-diff' } : null, [cur ? cur[1] : '-']);
        if (changed) td.appendChild(el('span', { class: 'sr-only', text: ' (changed)' }));
        return el('tr', null, [el('th', { scope: 'row', text: f[0] }), el('td', { text: f[1] }), td]);
      });
      compareBox.appendChild(el('h4', { text: 'Scenario A beside what is entered now' }));
      compareBox.appendChild(el('p', { class: 'kc-help', text: 'A was kept at ' + keptA.at + '. A changed figure is in bold.' }));
      compareBox.appendChild(el('table', null, [el('caption', { class: 'sr-only', text: 'Scenario A and the current calculation, figure by figure' }),
        el('thead', null, [el('tr', null, [el('th', { scope: 'col', text: 'Figure' }), el('th', { scope: 'col', text: 'Scenario A' }), el('th', { scope: 'col', text: 'Now' })])]),
        el('tbody', null, rows)]));
      compareBox.appendChild(el('div', { class: 'kc-actions' }, [
        el('button', { type: 'button', text: 'Keep this as A', onclick: keep }),
        el('button', { type: 'button', text: 'Clear scenario A', onclick: function () { keptA = null; draw(); say('Scenario A cleared.'); } })]));
      compareBox.hidden = false;
    }

    function draw() {
      var r = calc();
      results.innerHTML = '';
      figures(k, r).forEach(function (f) {
        results.appendChild(el('li', null, [el('p', { class: 'kc-q', text: f[0] }), el('p', { class: 'kc-a', text: f[1] }), el('p', { class: 'kc-how', text: how(f[0]) })]));
      });
      if (r.errors.length) results.appendChild(el('li', null, [el('p', { class: 'kc-how', text: r.errors[0] })]));
      advice.textContent = r.errors.length ? '' : (r.advice || '');
      advice.hidden = !advice.textContent;
      warn.textContent = r.warnings.join(' ');
      warn.hidden = !warn.textContent;
      drawCompare(r);
      return r;
    }

    function keep() {
      var r = calc(), figs = figures(k, r);
      if (!figs.length) { say('Enter numbers the calculator can work out first, then keep them as scenario A.'); return; }
      var at = '';
      try { at = new Date().toLocaleTimeString('en-PH', { hour: 'numeric', minute: '2-digit' }); } catch (_) { at = 'just now'; }   // empty-catch-allow: no locale data
      keptA = { figs: figs, at: at };
      draw();
      say('Kept as scenario A. Change any number to see A beside it.');
    }

    function link() { return location.href.replace(/#.*$/, '') + '#kpi=' + encode(state); }
    var copyBox = el('input', { type: 'url', class: 'kc-copy', readonly: '', 'aria-label': 'Link to this calculation', hidden: '' });
    var keepBtn = el('button', { type: 'button', text: 'Keep as scenario A', onclick: keep });
    var saveBtn = el('button', { type: 'button', text: 'Save on this device', onclick: function () {
      try { localStorage.setItem(STORE, encode(state)); say('Saved on this device. It opens here next time.'); }
      catch (_) { say('This browser would not save it (private mode?). Copy the share link instead - it holds the whole calculation.'); }
    } });
    var shareBtn = el('button', { type: 'button', text: 'Copy share link', onclick: function () {
      var u = link();
      try { history.replaceState(null, '', u); } catch (_) { /* empty-catch-allow: the link is still copied below */ }
      var done = function () { copyBox.hidden = true; say('Link copied. Anyone who opens it sees this calculation.'); };
      var show = function () { copyBox.value = u; copyBox.hidden = false; copyBox.focus(); copyBox.select(); say('Copy the link from the box above.'); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(u).then(done, show); else show();
    } });

    // the print sheet: what was entered, what it gives, what to do, and the standard - and when it was printed
    var sheet = el('div', { class: 'wh-kc-sheet', 'aria-hidden': 'true' });
    function fillSheet() {
      var r = calc();
      sheet.innerHTML = '';
      var stamp = '';
      try { stamp = new Date().toLocaleString('en-GB', { timeZone: 'Asia/Manila', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }) + ' PHT'; }
      catch (_) { stamp = new Date().toISOString(); }   // empty-catch-allow: no time zone data
      var specs = k === 'oee' ? FIELDS.oee[state.mode] : FIELDS.mtbf;
      sheet.appendChild(el('h2', { text: META[k].title }));
      sheet.appendChild(el('p', { text: 'Printed ' + stamp + ' from ' + location.href.replace(/#.*$/, '') }));
      sheet.appendChild(el('h4', { text: 'Inputs' }));
      sheet.appendChild(el('table', null, [el('tbody', null, specs.map(function (s) { return el('tr', null, [el('th', { text: s[1] }), el('td', { text: String(state[s[0]]) })]); }))]));
      sheet.appendChild(el('h4', { text: 'Result' }));
      var figs = figures(k, r);
      sheet.appendChild(figs.length ? el('table', null, [el('tbody', null, figs.map(function (f) { return el('tr', null, [el('th', { text: f[0] }), el('td', { text: f[1] }), el('td', { text: how(f[0]) })]); }))])
        : el('p', { text: r.errors[0] || r.advice || '' }));
      if (r.advice && figs.length) { sheet.appendChild(el('h4', { text: 'What to do' })); sheet.appendChild(el('p', { text: r.advice })); }
      if (r.warnings.length) sheet.appendChild(el('p', { text: r.warnings.join(' ') }));
      sheet.appendChild(el('h4', { text: 'Method and standard' }));
      sheet.appendChild(el('p', { text: META[k].method }));
      sheet.appendChild(el('p', { text: 'Standard: ' + META[k].standard }));
    }
    var printBtn = el('button', { type: 'button', class: 'kc-primary', text: 'Print or save as PDF', onclick: function () { fillSheet(); window.print(); } });
    window.addEventListener('beforeprint', function () { fillSheet(); document.body.classList.add('wh-kc-printing'); });
    window.addEventListener('afterprint', function () { document.body.classList.remove('wh-kc-printing'); });
    document.body.appendChild(sheet);

    root.appendChild(el('h3', { text: k === 'oee' ? 'Your line, your shift' : 'Your asset, your period' }));
    root.appendChild(el('p', { class: 'kc-help', text: k === 'oee'
      ? 'Enter one shift or one week from your records - or the three percentages, if you already have them. The worked example is filled in to start.'
      : 'Enter one asset over one period: how long it ran, how many times it failed, and how long the repairs took in total. The worked example is filled in to start.' }));
    if (modeBox) root.appendChild(modeBox);
    Object.keys(grids).forEach(function (g) { root.appendChild(grids[g]); });
    root.appendChild(el('h3', { text: 'What it gives' }));
    root.appendChild(results);
    root.appendChild(advice);
    root.appendChild(warn);
    root.appendChild(el('div', { class: 'kc-actions' }, [printBtn, keepBtn, shareBtn, saveBtn]));
    root.appendChild(copyBox);
    root.appendChild(said);
    root.appendChild(compareBox);

    showMode();
    draw();
    if (savedFrom === 'link') say('This calculation came from a shared link. Change anything - your copy is your own.');
    else if (savedFrom === 'device') say('Your saved calculation is back.');
    return { state: state, calc: calc };
  }

  var api = { oee: oee, mtbf: mtbf, mount: mount, encode: encode, decode: decode, WORLD: WORLD, DEF: DEF };
  if (typeof window !== 'undefined') {
    window.WhKpiCalc = api;
    // the page places this script right after its [data-wh-kpi-calc] element, so it is drawn during the parse and
    // nothing below it moves; a page that loads it elsewhere gets it at DOMContentLoaded
    var auto = function () { var n = document.querySelector('[data-wh-kpi-calc]'); if (n && !n.classList.contains('wh-kc')) mount(n); return !!n; };
    if (!auto() && document.readyState === 'loading') document.addEventListener('DOMContentLoaded', auto);
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
