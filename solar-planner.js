/* solar-planner.js - the off-grid solar power-station planner (ENH-S, 2026-10-22).
 *
 * Ian, 2026-10-14, by name: list the appliances, add up the daily watt-hours, size for the surge, choose the days of
 * autonomy, size the battery and the inverter, use the peak sun hours of the person's own area, size the charge
 * controller, then save, share and print the plan. Built ONCE here and used by both solar surfaces: the public
 * calculator (tools/solar-pv-calculator, no account, nothing leaves the page) and the Solar PV calc type in the
 * Engineering Design suite.
 *
 *   WhSolarPlanner.plan(input)   the sizing chain, a pure function (tools/test_solar_planner.mjs holds it to hand-worked cases)
 *   WhSolarPlanner.mount(el, o)  the planner UI in `el`. Options: o.onPlan(result) hears every change; o.onUse(result)
 *                                with o.useLabel adds the host page's own action (the Engineering Design suite fills its
 *                                calculation from the plan - the sentence it returns is said); o.shareBase is the address a
 *                                share link opens (the suite's own calculator, not the page's current state)
 *
 * The method (each step states its own numbers on screen):
 *   load Wh/day     = sum of watts x quantity x hours a day
 *   battery out     = load / (inverter efficiency x wiring efficiency)                    what the battery must deliver a day
 *   array in        = battery out / battery round-trip efficiency                         what the panels must put in a day
 *   battery bank    = battery out x days of autonomy / depth of discharge  (IEEE 1013 / IEEE 1562 stand-alone sizing)
 *   array Wp        = array in / (peak sun hours x module derate) x rainy-season margin  (IEEE 1562; PSH as the Engineering
 *                     Design suite's PAGASA values)
 *   inverter        = running load x 1.25, a standard size; its surge rating (taken as 2x for a few seconds - check the
 *                     datasheet) must cover the running load plus the largest motor's extra starting draw
 *   system voltage  = the lowest of 12, 24 or 48 V that keeps both the inverter's battery current and the charge current
 *                     within 100 A (a 1.65 kWp array on 12 V would need 172 A of charge current - two controllers and
 *                     thick cable - and 86 A on 24 V)
 *   charge controller = array W / system voltage x 1.25, MPPT (PEC 2017 Art. 6.90 / IEC 62509)
 */
(function () {
  'use strict';

  // Peak sun hours (annual average, h/day) - the values the Engineering Design suite's Solar PV calc already uses
  // (engineering-design.js), so the two surfaces give one answer for one place.
  var PSH = [
    ['Metro Manila', 4.5], ['Batangas', 4.6], ['Baguio', 4.2], ['Legazpi', 4.4], ['Iloilo', 4.7], ['Cebu', 4.8],
    ['Tacloban', 4.5], ['Cagayan de Oro', 4.6], ['Davao', 4.9], ['Zamboanga', 4.9]
  ];
  var CHEM = {
    lifepo4: { label: 'Lithium iron phosphate (LiFePO4)', short: 'LiFePO4 (lithium)', dod: 0.8, eff: 0.95 },
    leadacid: { label: 'Lead-acid deep cycle (flooded or AGM)', short: 'Lead-acid (flooded or AGM)', dod: 0.5, eff: 0.85 }
  };
  var INV_EFF = 0.93, WIRE_EFF = 0.97, DERATE = 0.85, INV_HEADROOM = 1.25, SURGE_OF_RATED = 2, CC_FACTOR = 1.25;
  var INV_SIZES = [300, 500, 600, 1000, 1500, 2000, 3000, 4000, 5000, 6000, 8000, 10000, 12000];
  var CC_SIZES = [10, 20, 30, 40, 50, 60, 80, 100];
  var VOLTS = [12, 24, 48], MAX_DC_A = 100;
  // Typical retail prices in the Philippines when this was written (2026). They are a starting point only; the planner
  // shows them, lets the person replace each one with a supplier's quote, and says so beside the total.
  var PRICES = { panelPerWp: 14, lifepo4PerKwh: 12000, leadacidPerKwh: 6500, inverterPerW: 10, controllerPerA: 180, bosPct: 15 };
  // Common loads, typical nameplate watts. Surge: how many times its running watts a load draws for the first second or
  // two - a compressor or a pump motor about 3x, a fan motor about 2x, an inverter-type compressor about 1.5x, a heater 1x.
  var PRESETS = [
    ['LED bulb', 9, 1, 6, 1], ['Electric fan', 60, 1, 8, 2], ['Refrigerator (non-inverter)', 120, 1, 24, 3],
    ['Refrigerator (inverter type)', 80, 1, 24, 1.5], ['LED TV (32 in)', 50, 1, 5, 1], ['Laptop', 60, 1, 6, 1],
    ['Phone charging', 10, 2, 3, 1], ['Wi-Fi router', 12, 1, 24, 1], ['CCTV (4 cameras + recorder)', 40, 1, 24, 1],
    ['Water pump (1/2 HP)', 450, 1, 1, 3], ['Rice cooker', 600, 1, 1, 1], ['Aircon 1 HP (inverter type)', 700, 1, 6, 1.5],
    ['Aircon 1 HP (window, non-inverter)', 900, 1, 6, 3]
  ];
  var EXAMPLE = [['LED bulb', 9, 6, 6, 1], ['Electric fan', 60, 2, 8, 2], ['Refrigerator (inverter type)', 80, 1, 24, 1.5],
                 ['LED TV (32 in)', 50, 1, 5, 1], ['Phone charging', 10, 3, 3, 1], ['Water pump (1/2 HP)', 450, 1, 1, 3]];

  function num(v, d) { var n = Number(v); return isFinite(n) ? n : d; }
  function up(sizes, need) { for (var i = 0; i < sizes.length; i++) if (sizes[i] >= need) return sizes[i]; return null; }

  // ── the sizing chain ────────────────────────────────────────────────────────────────────────────────────────────
  function plan(input) {
    input = input || {};
    var chem = CHEM[input.chemistry] || CHEM.lifepo4;
    var psh = num(input.psh, 4.5), days = Math.max(0, num(input.days, 1)), margin = Math.max(1, num(input.margin, 1));
    var panelWp = Math.max(1, num(input.panelWp, 550));
    var price = {};
    for (var k in PRICES) price[k] = num(input.prices && input.prices[k], PRICES[k]);
    var rows = (input.appliances || []).map(function (a) {
      var w = Math.max(0, num(a.watts, 0)), q = Math.max(0, Math.round(num(a.qty, 1))), h = Math.min(24, Math.max(0, num(a.hours, 0)));
      var s = Math.max(1, num(a.surge, 1));
      return { name: String(a.name || 'Appliance'), watts: w, qty: q, hours: h, surge: s, wh: w * q * h, runW: w * q };
    }).filter(function (r) { return r.watts > 0 && r.qty > 0; });
    var loadWh = rows.reduce(function (t, r) { return t + r.wh; }, 0);
    var peakW = rows.reduce(function (t, r) { return t + r.runW; }, 0);
    // the largest single start on top of everything else running: one unit of the load with the largest extra draw
    var big = null, extra = 0;
    rows.forEach(function (r) { var e = r.watts * (r.surge - 1); if (e > extra) { extra = e; big = r; } });
    var surgeW = peakW + extra;
    var invNeed = peakW * INV_HEADROOM;
    // nothing listed, nothing sized: a station for no load is no inverter, no controller and no cost
    var invW = peakW > 0 ? up(INV_SIZES, Math.max(invNeed, surgeW / SURGE_OF_RATED)) : 0;
    var batteryOutWh = loadWh / (INV_EFF * WIRE_EFF);
    var arrayInWh = batteryOutWh / chem.eff;
    var arrayWpNeed = psh > 0 ? arrayInWh / (psh * DERATE) * margin : 0;
    var panels = arrayWpNeed > 0 ? Math.ceil(arrayWpNeed / panelWp) : 0;
    var arrayWp = panels * panelWp;
    var sysV = 48;
    for (var vi = 0; vi < VOLTS.length; vi++) {
      if ((invW === null ? Infinity : invW) / VOLTS[vi] <= MAX_DC_A && arrayWp / VOLTS[vi] * CC_FACTOR <= MAX_DC_A) { sysV = VOLTS[vi]; break; }
    }
    var bankWh = days > 0 ? batteryOutWh * days / chem.dod : 0;
    var bankAh = bankWh / sysV;
    var ccA = arrayWp / sysV * CC_FACTOR;
    var ccSize = ccA > 0 ? up(CC_SIZES, ccA) : 0;
    var ccCount = ccA <= 0 ? 0 : ccSize ? 1 : Math.ceil(ccA / 100);
    if (ccA > 0 && !ccSize) ccSize = 100;
    var perKwh = input.chemistry === 'leadacid' ? price.leadacidPerKwh : price.lifepo4PerKwh;
    var cost = { panels: arrayWp * price.panelPerWp, battery: bankWh / 1000 * perKwh, inverter: (invW || 0) * price.inverterPerW,
                 controller: ccSize * ccCount * price.controllerPerA };
    cost.equipment = cost.panels + cost.battery + cost.inverter + cost.controller;
    cost.bos = cost.equipment * price.bosPct / 100;
    cost.total = cost.equipment + cost.bos;
    return {
      appliances: rows, loadWh: loadWh, peakW: peakW, surgeW: surgeW, surgeFrom: big ? big.name : null, surgeExtraW: extra,
      losses: { inverter: INV_EFF, wiring: WIRE_EFF, battery: chem.eff, derate: DERATE }, batteryOutWh: batteryOutWh,
      arrayInWh: arrayInWh, chemistry: chem.label, dod: chem.dod, days: days, bankWh: bankWh, bankAh: bankAh, systemV: sysV,
      place: input.place || null, psh: psh, margin: margin, panelWp: panelWp, arrayWpNeed: arrayWpNeed, panels: panels, arrayWp: arrayWp,
      inverter: { needW: invNeed, sizeW: invW, surgeRatingW: invW ? invW * SURGE_OF_RATED : null, surgeNeedW: surgeW, tooBig: peakW > 0 && !invW },
      controller: { amps: ccA, sizeA: ccSize, count: ccCount }, prices: price, cost: cost
    };
  }

  // ── state: what a plan is, as saved and shared ─────────────────────────────────────────────────────────────────
  function encode(st) {
    var s = JSON.stringify(st);
    try { return btoa(unescape(encodeURIComponent(s))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); } catch (_) { return ''; }
  }
  function decode(t) {
    try {
      var b = String(t).replace(/-/g, '+').replace(/_/g, '/');
      while (b.length % 4) b += '=';
      var o = JSON.parse(decodeURIComponent(escape(atob(b))));
      return o && o.v === 1 ? o : null;
    } catch (_) { return null; }
  }
  var STORE = 'wh_solar_plan_v1';

  // ── the UI ─────────────────────────────────────────────────────────────────────────────────────────────────────
  var CSS = '' +
    // the planner is its own size container: a row's layout follows the planner's width (a 700 px article column at
    // 1280, the full width of a suite panel), not the window's
    '.wh-sp{--sp-line:rgba(255,255,255,0.10);--sp-muted:rgba(244,246,250,0.80);color:var(--wh-cloud,#F4F6FA);container-type:inline-size}' +
    '.wh-sp h3{margin:1.75rem 0 0.5rem;font-size:1.125rem;font-weight:700;line-height:1.35}' +
    '.wh-sp h3:first-child{margin-top:0.25rem}' +
    '.wh-sp p{margin:0 0 0.75rem}' +
    '.wh-sp .sp-help{font-size:0.875rem;color:var(--sp-muted);line-height:1.55}' +
    '.wh-sp label{display:block;font-size:0.75rem;font-weight:600;color:var(--sp-muted);margin:0 0 4px}' +
    '.wh-sp input,.wh-sp select{width:100%;box-sizing:border-box;min-height:44px;padding:8px 10px;border-radius:8px;' +
      'border:1px solid rgba(255,255,255,0.18);background:var(--wh-navy-mid,#1F2E45);color:var(--wh-cloud,#F4F6FA);font:inherit;font-size:1rem}' +
    '.wh-sp input:focus-visible,.wh-sp select:focus-visible,.wh-sp button:focus-visible{outline:2px solid var(--wh-orange,#F7A21B);outline-offset:2px}' +
    '.wh-sp input[type=number]{font-variant-numeric:tabular-nums}' +
    '.wh-sp button{min-height:44px;padding:0 16px;border-radius:8px;font:inherit;font-size:0.875rem;font-weight:600;cursor:pointer;' +
      'border:1px solid rgba(255,255,255,0.22);background:transparent;color:var(--wh-cloud,#F4F6FA)}' +
    '.wh-sp button:hover{border-color:rgba(255,255,255,0.40)}' +
    '.wh-sp button.sp-primary{background:var(--wh-orange,#F7A21B);border-color:var(--wh-orange,#F7A21B);color:var(--wh-navy,#162032)}' +
    '.wh-sp button.sp-primary:hover{background:var(--wh-orange-light,#FDB94A);border-color:var(--wh-orange-light,#FDB94A)}' +
    '.wh-sp .sp-list{list-style:none;margin:0 0 0.75rem;padding:0;border-top:1px solid var(--sp-line)}' +
    '.wh-sp .sp-list li{list-style:none;margin:0;padding:12px 0;border-bottom:1px solid var(--sp-line);display:grid;gap:8px 10px;' +
      'grid-template-columns:repeat(3,minmax(0,1fr));align-items:end}' +
    '.wh-sp .sp-list .sp-name{grid-column:1/-1}' +
    '.wh-sp .sp-list .sp-surge{grid-column:1/3}' +
    '.wh-sp .sp-list .sp-del button{width:100%}' +
    // a mid-width planner (the 700 px article column): name, watts, how many and hours on one line; surge and Remove below
    '@container (min-width:480px){.wh-sp .sp-list li{grid-template-columns:minmax(0,2fr) repeat(3,minmax(0,1fr))}' +
      '.wh-sp .sp-list .sp-name{grid-column:auto}.wh-sp .sp-list .sp-surge{grid-column:1/4}}' +
    '@container (min-width:880px){.wh-sp .sp-list li{grid-template-columns:minmax(0,2fr) repeat(3,minmax(0,0.9fr)) minmax(0,1.7fr) auto}' +
      '.wh-sp .sp-list .sp-surge{grid-column:auto}}' +
    '.wh-sp .sp-empty{padding:14px 0;color:var(--sp-muted);font-size:0.875rem}' +
    '.wh-sp .sp-add{display:flex;flex-wrap:wrap;gap:8px;align-items:end;margin-bottom:0.5rem}' +
    '.wh-sp .sp-add>div{flex:1 1 220px}' +
    '.wh-sp .sp-grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr));align-items:end}' +
    '.wh-sp .sp-result{margin:0;padding:0;list-style:none;border-top:1px solid var(--sp-line)}' +
    '.wh-sp .sp-result>li{list-style:none;margin:0;padding:14px 0;border-bottom:1px solid var(--sp-line)}' +
    '.wh-sp .sp-q{font-weight:700;font-size:0.95rem;margin:0 0 4px}' +
    '.wh-sp .sp-a{font-size:1.125rem;font-weight:700;font-variant-numeric:tabular-nums;color:var(--wh-orange-light,#FDB94A);margin:0 0 4px}' +
    '.wh-sp .sp-how{font-size:0.875rem;color:var(--sp-muted);line-height:1.55;font-variant-numeric:tabular-nums;margin:0}' +
    '.wh-sp .sp-warn{color:var(--wh-red-text,#FDC9C9)}' +
    '.wh-sp .sp-actions{display:flex;flex-wrap:wrap;gap:8px;margin:1rem 0 0.25rem}' +
    '.wh-sp .sp-said{min-height:1.5em;font-size:0.875rem;color:var(--sp-muted);margin:0.25rem 0 0}' +
    '.wh-sp details{margin:0.75rem 0}' +
    '.wh-sp summary{cursor:pointer;min-height:44px;display:flex;align-items:center;font-weight:600}' +
    '.wh-sp table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}' +
    '.wh-sp th,.wh-sp td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--sp-line);vertical-align:top}' +
    '.wh-sp .sp-copy{margin-top:8px}' +
    '.wh-sp-sheet{display:none}' +
    '@media print{body.wh-sp-printing>*{display:none !important}' +
      'body.wh-sp-printing{background:#fff !important}' +
      'body.wh-sp-printing>.wh-sp-sheet{display:block !important;position:static !important;color:#000;background:#fff;font:11pt/1.45 Poppins,Arial,sans-serif}' +
      // a host page's own print rule may hide everything by visibility (the suite's report does): the sheet asks back
      'body.wh-sp-printing>.wh-sp-sheet,body.wh-sp-printing>.wh-sp-sheet *{visibility:visible !important}' +
      '.wh-sp-sheet h2{font-size:16pt;margin:0 0 6pt}.wh-sp-sheet h4{font-size:12pt;margin:12pt 0 4pt}' +
      '.wh-sp-sheet table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}' +
      '.wh-sp-sheet th,.wh-sp-sheet td{text-align:left;border-bottom:1px solid #999;padding:3pt 5pt;vertical-align:top}' +
      '.wh-sp-sheet p{margin:0 0 6pt}}';

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
  var f0 = function (n) { return Math.round(n).toLocaleString('en-PH'); };
  var f1 = function (n) { return (Math.round(n * 10) / 10).toLocaleString('en-PH'); };
  var peso = function (n) { return '₱' + Math.round(n).toLocaleString('en-PH'); };
  var pct = function (n) { return Math.round(n * 100) + '%'; };
  var uid = 0;

  function mount(root, opts) {
    opts = opts || {};
    if (!root) return null;
    if (!document.getElementById('wh-sp-css')) {
      var st = document.createElement('style'); st.id = 'wh-sp-css'; st.textContent = CSS;
      (document.head || document.documentElement).appendChild(st);
    }
    var id = 'sp' + (++uid);
    var state = { v: 1, a: [], loc: 0, psh: PSH[0][1], days: 1, chem: 'lifepo4', wp: 550, margin: 1.25, prices: {} };
    var fromLink = /(?:^|[#&])plan=([^&]+)/.exec(location.hash || '');
    var loaded = fromLink ? decode(fromLink[1]) : null, savedFrom = loaded ? 'link' : null;
    if (!loaded) { try { loaded = decode(localStorage.getItem(STORE) || ''); if (loaded) savedFrom = 'device'; } catch (_) { loaded = null; } }
    if (loaded) for (var k in state) if (loaded[k] !== undefined) state[k] = loaded[k];

    root.classList.add('wh-sp');
    root.innerHTML = '';
    var list = el('ul', { class: 'sp-list', 'aria-label': 'Appliances the station will power' });
    var empty = el('p', { class: 'sp-empty', text: 'No appliances yet. Add the first one below, or start from a small home and change it.' });
    var presetSel = el('select', { id: id + '-preset' }, [el('option', { value: '', text: 'Choose a common appliance' })]
      .concat(PRESETS.map(function (p, i) { return el('option', { value: String(i), text: p[0] + ' (' + p[1] + ' W)' }); })));
    var said = el('p', { class: 'sp-said', role: 'status', 'aria-live': 'polite' });
    var results = el('ol', { class: 'sp-result', 'aria-label': 'Your solar power station, step by step' });
    // the spec sheet lives outside the page's layout - a direct child of <body> that only print shows - so a printed
    // plan is the sheet alone, not the sheet laid over a page of hidden blocks
    var sheet = document.querySelector('body > .wh-sp-sheet') || el('div', { class: 'wh-sp-sheet', 'aria-hidden': 'true' });
    if (!sheet.parentNode) document.body.appendChild(sheet);
    var copyBox = el('input', { class: 'sp-copy', type: 'text', readonly: 'readonly', 'aria-label': 'Share link', hidden: 'hidden' });

    function row(a, i) {
      var f = function (key, label, type, val, attrs) {
        var inp = el('input', Object.assign({ id: id + '-' + key + i, type: type, value: String(val), 'data-k': key, 'data-i': String(i) }, attrs || {}));
        inp.addEventListener('input', onEdit);
        return el('div', { class: 'sp-' + key }, [el('label', { for: inp.id, text: label }), inp]);
      };
      var surge = el('select', { id: id + '-surge' + i, 'data-k': 'surge', 'data-i': String(i) },
        [[1, 'None (lights, electronics)'], [1.5, '1.5x (inverter-type motor)'], [2, '2x (fan motor)'], [3, '3x (compressor or pump)']]
          .map(function (o) { var op = el('option', { value: String(o[0]), text: o[1] }); if (Number(a[4]) === o[0]) op.selected = true; return op; }));
      surge.addEventListener('change', onEdit);
      return el('li', null, [
        f('name', 'Appliance', 'text', a[0], { maxlength: '60', autocomplete: 'off' }),
        f('watts', 'Watts', 'number', a[1], { min: '0', step: 'any', inputmode: 'decimal' }),
        f('qty', 'How many', 'number', a[2], { min: '0', step: '1', inputmode: 'numeric' }),
        f('hours', 'Hours a day', 'number', a[3], { min: '0', max: '24', step: 'any', inputmode: 'decimal' }),
        el('div', { class: 'sp-surge' }, [el('label', { for: surge.id, text: 'Starting surge' }), surge]),
        el('div', { class: 'sp-del' }, [el('button', { type: 'button', 'data-del': String(i), text: 'Remove',
          'aria-label': 'Remove ' + (a[0] || 'appliance') })])
      ]);
    }
    function drawList(focusLast) {
      list.innerHTML = '';
      state.a.forEach(function (a, i) { list.appendChild(row(a, i)); });
      empty.hidden = state.a.length > 0;
      if (focusLast && state.a.length) { var x = list.lastElementChild.querySelector('input'); if (x) x.focus(); }
    }
    function onEdit(ev) {
      var t = ev.target, i = Number(t.getAttribute('data-i')), k = t.getAttribute('data-k');
      var col = { name: 0, watts: 1, qty: 2, hours: 3, surge: 4 }[k];
      if (!(i >= 0) || col == null) return;
      state.a[i][col] = col === 0 ? t.value : Number(t.value);
      if (col === 0) { var d = list.children[i] && list.children[i].querySelector('[data-del]'); if (d) d.setAttribute('aria-label', 'Remove ' + (t.value || 'appliance')); }
      recompute();
    }
    list.addEventListener('click', function (ev) {
      var b = ev.target.closest && ev.target.closest('[data-del]');
      if (!b) return;
      state.a.splice(Number(b.getAttribute('data-del')), 1);
      drawList(false); recompute();
      say('Removed. ' + state.a.length + ' appliance' + (state.a.length === 1 ? '' : 's') + ' in the list.');
    });

    // where, how long, which battery, which panel
    var locSel = el('select', { id: id + '-loc' }, PSH.map(function (p, i) { return el('option', { value: String(i), text: p[0] + ' (' + p[1] + ' h)' }); })
      .concat([el('option', { value: 'custom', text: 'Another place - enter its sun hours' })]));
    var pshIn = el('input', { id: id + '-psh', type: 'number', min: '1', max: '8', step: '0.1', inputmode: 'decimal', value: String(state.psh) });
    var pshWrap = el('div', null, [el('label', { for: pshIn.id, text: 'Peak sun hours a day (PAGASA)' }), pshIn]);
    var daysIn = el('input', { id: id + '-days', type: 'number', min: '0', max: '7', step: '0.5', inputmode: 'decimal', value: String(state.days) });
    var chemSel = el('select', { id: id + '-chem' }, Object.keys(CHEM).map(function (c) { return el('option', { value: c, text: CHEM[c].short }); }));
    var wpSel = el('select', { id: id + '-wp' }, [400, 450, 550, 600].map(function (w) { return el('option', { value: String(w), text: w + ' Wp panels' }); }));
    var marginSel = el('select', { id: id + '-margin' }, [[1.25, '+25% (recommended)'], [1, 'None (annual average sun)']]
      .map(function (o) { return el('option', { value: String(o[0]), text: o[1] }); }));
    function syncInputs() {
      if (state.loc === 'custom') locSel.value = 'custom'; else locSel.value = String(state.loc);
      pshWrap.hidden = state.loc !== 'custom';
      pshIn.value = String(state.psh); daysIn.value = String(state.days); chemSel.value = state.chem;
      wpSel.value = String(state.wp); marginSel.value = String(state.margin);
    }
    locSel.addEventListener('change', function () {
      if (locSel.value === 'custom') { state.loc = 'custom'; pshWrap.hidden = false; pshIn.focus(); }
      else { state.loc = Number(locSel.value); state.psh = PSH[state.loc][1]; pshWrap.hidden = true; }
      recompute();
    });
    pshIn.addEventListener('input', function () { state.psh = Number(pshIn.value) || 0; recompute(); });
    daysIn.addEventListener('input', function () { state.days = Number(daysIn.value) || 0; recompute(); });
    chemSel.addEventListener('change', function () { state.chem = chemSel.value; recompute(); });
    wpSel.addEventListener('change', function () { state.wp = Number(wpSel.value); recompute(); });
    marginSel.addEventListener('change', function () { state.margin = Number(marginSel.value); recompute(); });

    // prices: a starting point the person replaces
    var priceKeys = [['panelPerWp', 'Solar panels, pesos per watt-peak'], ['lifepo4PerKwh', 'LiFePO4 battery, pesos per kWh'],
                     ['leadacidPerKwh', 'Lead-acid battery, pesos per kWh'], ['inverterPerW', 'Inverter, pesos per watt'],
                     ['controllerPerA', 'MPPT charge controller, pesos per amp'], ['bosPct', 'Cables, breakers, fuses and mounting, % of the parts']];
    var priceBox = el('div', { class: 'sp-grid' }, priceKeys.map(function (p) {
      var inp = el('input', { id: id + '-p-' + p[0], type: 'number', min: '0', step: 'any', inputmode: 'decimal',
                              value: String(state.prices[p[0]] != null ? state.prices[p[0]] : PRICES[p[0]]) });
      inp.addEventListener('input', function () { state.prices[p[0]] = Number(inp.value); recompute(); });
      return el('div', null, [el('label', { for: inp.id, text: p[1] }), inp]);
    }));

    function say(t) { said.textContent = t; }
    function current() {
      return { appliances: state.a.map(function (a) { return { name: a[0], watts: a[1], qty: a[2], hours: a[3], surge: a[4] }; }),
               place: state.loc === 'custom' || !PSH[state.loc] ? null : PSH[state.loc][0],
               psh: state.psh, days: state.days, chemistry: state.chem, panelWp: state.wp, margin: state.margin, prices: state.prices };
    }
    function li(q, a, how, warn) {
      return el('li', null, [el('p', { class: 'sp-q', text: q }), el('p', { class: 'sp-a' + (warn ? ' sp-warn' : ''), text: a }),
                             how ? el('p', { class: 'sp-how', text: how }) : null]);
    }
    function recompute() {
      var r = plan(current());
      results.innerHTML = '';
      if (!r.appliances.length) {
        results.appendChild(el('li', null, [el('p', { class: 'sp-how', text: 'The station is sized from what it powers - add an appliance to see each step.' })]));
        sheet.innerHTML = '';
        if (opts.onPlan) opts.onPlan(r);
        return r;
      }
      var L = r.losses;
      results.appendChild(li('Daily energy', f0(r.loadWh) + ' Wh a day',
        'The appliances use ' + f0(r.loadWh) + ' Wh. Losses stated: inverter ' + pct(L.inverter) + ', wiring ' + pct(L.wiring) + ', battery round trip ' +
        pct(L.battery) + ' - so the battery delivers ' + f0(r.batteryOutWh) + ' Wh and the panels must put in ' + f0(r.arrayInWh) + ' Wh a day.'));
      results.appendChild(li('Peak load and surge', f0(r.peakW) + ' W running, ' + f0(r.surgeW) + ' W at a start',
        r.surgeFrom ? 'If everything runs at once: ' + f0(r.peakW) + ' W. The largest start is the ' + r.surgeFrom + ', adding ' + f0(r.surgeExtraW) +
          ' W for a second or two.' : 'Everything runs at once: ' + f0(r.peakW) + ' W. Nothing in the list starts with a surge.'));
      results.appendChild(li('Inverter', r.inverter.tooBig ? 'Above 12,000 W - split the load across two systems'
        : f0(r.inverter.sizeW) + ' W pure sine wave, ' + r.systemV + ' V', r.inverter.tooBig ? null
        : 'Running load x 1.25 = ' + f0(r.inverter.needW) + ' W. Its surge rating (usually 2x for a few seconds, ' + f0(r.inverter.surgeRatingW) +
          ' W - check the datasheet) covers the ' + f0(r.surgeW) + ' W start.', r.inverter.tooBig));
      results.appendChild(li('Battery bank', r.days > 0 ? f1(r.bankWh / 1000) + ' kWh (' + f0(r.bankAh) + ' Ah at ' + r.systemV + ' V)' : 'No backup days chosen',
        r.days > 0 ? r.chemistry + ': ' + f0(r.batteryOutWh) + ' Wh x ' + r.days + ' day' + (r.days === 1 ? '' : 's') + ' without sun / ' + pct(r.dod) +
          ' depth of discharge.' : 'With 0 days, the battery only carries the night - most off-grid homes choose 1 to 2 days.'));
      results.appendChild(li('Solar panels', r.panels + ' x ' + r.panelWp + ' Wp = ' + f1(r.arrayWp / 1000) + ' kWp',
        f0(r.arrayInWh) + ' Wh / (' + r.psh + ' sun hours x ' + pct(L.derate) + ' for heat, dust and mismatch)' +
          (r.margin > 1 ? ' x ' + r.margin + ' rainy-season margin' : '') + ' = ' + f0(r.arrayWpNeed) + ' Wp needed.'));
      results.appendChild(li('Charge controller', r.controller.count > 1 ? r.controller.count + ' x ' + r.controller.sizeA + ' A MPPT at ' + r.systemV + ' V'
        : r.controller.sizeA + ' A MPPT at ' + r.systemV + ' V',
        f0(r.arrayWp) + ' Wp / ' + r.systemV + ' V x 1.25 = ' + f1(r.controller.amps) + ' A. MPPT, because a ' + r.panelWp +
          ' Wp panel runs near 40 V, far above the battery - a PWM controller would waste the difference.'));
      results.appendChild(li('Cost estimate', peso(r.cost.total),
        'Panels ' + peso(r.cost.panels) + ', battery ' + peso(r.cost.battery) + ', inverter ' + peso(r.cost.inverter) + ', controller ' +
          peso(r.cost.controller) + ', cables, breakers and mounting ' + peso(r.cost.bos) + '. These prices are a starting point - replace them with your supplier\'s quote below.'));
      drawSheet(r);
      if (opts.onPlan) opts.onPlan(r);
      return r;
    }
    function drawSheet(r) {
      var rowsT = r.appliances.map(function (a) { return '<tr><td>' + esc(a.name) + '</td><td>' + f0(a.watts) + ' W</td><td>' + a.qty + '</td><td>' + f1(a.hours) + ' h</td><td>' + f0(a.wh) + ' Wh</td></tr>'; }).join('');
      sheet.innerHTML = '<h2>Solar power station - spec sheet</h2>' +
        '<p>Off-grid, ' + r.systemV + ' V. Sun: ' + r.psh + ' peak sun hours a day' + (r.margin > 1 ? ', +25% for the rainy season' : '') +
        '. Backup: ' + r.days + ' day' + (r.days === 1 ? '' : 's') + ' without sun.</p>' +
        '<h4>What to buy</h4><table><tbody>' +
        '<tr><th>Solar panels</th><td>' + r.panels + ' x ' + r.panelWp + ' Wp (' + f1(r.arrayWp / 1000) + ' kWp)</td></tr>' +
        '<tr><th>Battery bank</th><td>' + f1(r.bankWh / 1000) + ' kWh, ' + f0(r.bankAh) + ' Ah at ' + r.systemV + ' V - ' + esc(r.chemistry) + ', ' + pct(r.dod) + ' depth of discharge</td></tr>' +
        '<tr><th>Inverter</th><td>' + (r.inverter.tooBig ? 'above 12,000 W - split the load' : f0(r.inverter.sizeW) + ' W continuous pure sine wave, ' + r.systemV + ' V input, surge at least ' + f0(r.surgeW) + ' W') + '</td></tr>' +
        '<tr><th>Charge controller</th><td>' + r.controller.count + ' x ' + r.controller.sizeA + ' A MPPT, ' + r.systemV + ' V battery</td></tr>' +
        '<tr><th>Estimated cost</th><td>' + peso(r.cost.total) + ' (prices to confirm with your supplier)</td></tr></tbody></table>' +
        '<h4>Loads</h4><table><thead><tr><th>Appliance</th><th>Watts</th><th>Qty</th><th>Hours a day</th><th>Energy</th></tr></thead><tbody>' + rowsT +
        '<tr><th>Total</th><td>' + f0(r.peakW) + ' W running</td><td></td><td></td><td>' + f0(r.loadWh) + ' Wh a day</td></tr></tbody></table>' +
        '<p>Method: IEEE 1562 and IEEE 1013 stand-alone sizing; installation to PEC 2017 Article 6.90 by a licensed electrician. Planned with WorkHive\'s free solar planner.</p>';
    }
    function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

    function add(p) {
      state.a.push([p[0], p[1], p[2], p[3], p[4]]);
      drawList(true); recompute();
      say(p[0] + ' added. ' + state.a.length + ' appliance' + (state.a.length === 1 ? '' : 's') + ' in the list.');
    }
    var addBtn = el('button', { type: 'button', text: 'Add appliance', onclick: function () {
      var i = presetSel.value;
      add(i === '' ? ['Appliance', 100, 1, 1, 1] : PRESETS[Number(i)]);
      presetSel.value = '';
    } });
    var exampleBtn = el('button', { type: 'button', text: 'Start from a small home', onclick: function () {
      state.a = EXAMPLE.map(function (e) { return e.slice(); });
      drawList(false); recompute(); say('A small home loaded: ' + state.a.length + ' appliances. Change any of them.');
    } });
    function link() {
      var base = typeof opts.shareBase === 'string' ? opts.shareBase : location.href.replace(/#.*$/, '');
      return base + '#plan=' + encode(state);
    }
    var saveBtn = el('button', { type: 'button', text: 'Save on this device', onclick: function () {
      try { localStorage.setItem(STORE, encode(state)); say('Saved on this device. It opens here next time.'); }
      catch (_) { say('This browser would not save it (private mode?). Copy the share link instead - it holds the whole plan.'); }
    } });
    var shareBtn = el('button', { type: 'button', text: 'Copy share link', onclick: function () {
      var u = link();
      try { history.replaceState(null, '', u); } catch (_) { /* empty-catch-allow: the link is still copied below */ }
      var done = function () { copyBox.hidden = true; say('Link copied. Anyone who opens it sees this plan.'); };
      // no clipboard (an older browser, a blocked permission): the link goes in a box, selected, to copy by hand
      var show = function () { copyBox.value = u; copyBox.hidden = false; copyBox.focus(); copyBox.select(); say('Copy the link from the box above.'); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(u).then(done, show); else show();
    } });
    // the host page's own action with the plan, when it has one - it is then the primary action, print a secondary one
    var useBtn = typeof opts.onUse === 'function' ? el('button', { type: 'button', class: 'sp-primary', text: opts.useLabel || 'Use this plan',
      onclick: function () {
        if (!state.a.length) { say('Add an appliance first - the plan is sized from what it powers.'); return; }
        var r = recompute(), t = '';
        try { t = opts.onUse(r) || ''; } catch (_) { t = 'The plan could not be carried over - the numbers above still stand.'; }
        say(t || 'Done.');
      } }) : null;
    var printBtn = el('button', { type: 'button', class: useBtn ? '' : 'sp-primary', text: 'Print spec sheet', onclick: function () {
      if (!state.a.length) { say('Add an appliance first - the spec sheet lists what the station powers.'); return; }
      recompute(); window.print();
    } });
    // the browser's own Print (Ctrl+P, the share menu) prints the sheet too, once there is a plan to print
    window.addEventListener('beforeprint', function () { if (state.a.length) document.body.classList.add('wh-sp-printing'); });
    window.addEventListener('afterprint', function () { document.body.classList.remove('wh-sp-printing'); });

    root.appendChild(el('h3', { text: 'What will the station power?' }));
    root.appendChild(el('p', { class: 'sp-help', text: 'List each appliance with its watts (on its nameplate or charger), how many, and how long it runs a day.' }));
    root.appendChild(list);
    root.appendChild(empty);
    root.appendChild(el('div', { class: 'sp-add' }, [el('div', null, [el('label', { for: presetSel.id, text: 'Add an appliance' }), presetSel]), addBtn, exampleBtn]));
    root.appendChild(el('h3', { text: 'Where is it, and how long must it run without sun?' }));
    root.appendChild(el('div', { class: 'sp-grid' }, [
      el('div', null, [el('label', { for: locSel.id, text: 'Nearest place (PAGASA peak sun hours)' }), locSel]), pshWrap,
      el('div', null, [el('label', { for: daysIn.id, text: 'Days the battery carries without sun' }), daysIn]),
      el('div', null, [el('label', { for: chemSel.id, text: 'Battery' }), chemSel]),
      el('div', null, [el('label', { for: wpSel.id, text: 'Panel size' }), wpSel]),
      el('div', null, [el('label', { for: marginSel.id, text: 'Rainy-season margin' }), marginSel])
    ]));
    root.appendChild(el('h3', { text: 'Your station, step by step' }));
    root.appendChild(results);
    root.appendChild(el('details', null, [el('summary', { text: 'Prices used for the estimate' }),
      el('p', { class: 'sp-help', text: 'Typical 2026 retail prices in the Philippines - replace them with your supplier\'s quote.' }), priceBox]));
    root.appendChild(el('div', { class: 'sp-actions' }, [useBtn, printBtn, shareBtn, saveBtn]));
    root.appendChild(copyBox);
    root.appendChild(said);

    syncInputs();
    drawList(false);
    recompute();
    if (savedFrom === 'link') say('This plan came from a shared link. Change anything - your copy is your own.');
    else if (savedFrom === 'device') say('Your saved plan is back.');
    return { plan: function () { return plan(current()); }, state: state };
  }

  var api = { plan: plan, mount: mount, encode: encode, decode: decode, PSH: PSH, PRESETS: PRESETS, PRICES: PRICES, CHEM: CHEM };
  if (typeof window !== 'undefined') {
    window.WhSolarPlanner = api;
    // the page places this script right after its [data-wh-solar-planner] element, so the element is already parsed:
    // the planner is drawn now, during the parse, and nothing below it moves when it appears. A page that loads the
    // script elsewhere gets it at DOMContentLoaded.
    var auto = function () { var n = document.querySelector('[data-wh-solar-planner]'); if (n && !n.classList.contains('wh-sp')) mount(n); return !!n; };
    if (!auto() && document.readyState === 'loading') document.addEventListener('DOMContentLoaded', auto);
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
