/* ============================================================================
 * analytics_correctness.js — exhaustive per-tile parity spec for the Analytics
 * Engine, driven through the UFAI battery's Correctness pillar (T3 oracle parity).
 * ============================================================================
 * WHY: analytics.html is a SOURCE OF TRUTH — hive/asset-hub/predictive/shift-brain
 * read its computations. So EVERY rendered tile must equal the EXACT orchestrator
 * field the renderer reads. This file encodes that mapping (grounded in the
 * analytics render functions + the live orchestrator field inventory) and, given a
 * phase's oracle response, scrapes the rendered DOM and emits the `parity[]` array
 * for `window.__UFAI.run({ parity })`.
 *
 * THE TRAP this guards against (same-NAMED ≠ same-DERIVATION): the OEE table's
 * "Availability" column = `oee.oee_by_asset[].availability_pct` (operational, ISO
 * 22400, e.g. 96.1%), which is NOT `availability.availability_by_asset[].
 * availability_pct` (reliability = MTBF/(MTBF+MTTR), ISO 14224, e.g. 99.2%). Both
 * are rendered; the manifest pins each tile to the field its renderer ACTUALLY uses.
 * A GREEN 30/30 result PROVES the mapping; a RED one is investigated (wrong-field
 * vs wrong-value) before being called a bug.
 *
 * USAGE (per phase, after the phase has rendered):
 *   1. install: browser_evaluate(fn = <this file>)              // window.__ANALYTICS_PARITY
 *   2. oracle = POST analytics-orchestrator {phase,...}         // the source of truth
 *   3. spec   = window.__ANALYTICS_PARITY.build(phase, oracle)  // scrapes DOM + pairs
 *   4. run    = await window.__UFAI.run({ pageId:'analytics', parity: spec.parity })
 *      → run.correctness.major === 0 ⇔ every tile == its oracle field.
 * ==========================================================================*/
() => {
  const V = '1.0.0';

  // ── helpers ────────────────────────────────────────────────────────────────
  const path = (o, p) => p.split('.').reduce((a, k) => (a == null ? a : a[k]), o);
  const num = (s) => { const m = String(s == null ? '' : s).replace(/[, ]/g, '').match(/-?\d+(?:\.\d+)?/); return m ? parseFloat(m[0]) : null; };
  const norm = (s) => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
  const round = (n, d = 0) => (n == null ? null : Math.round(n * 10 ** d) / 10 ** d);
  const avg = (xs) => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;

  // find a rendered .data-table whose header row contains ALL of `headerHas`.
  const findTable = (headerHas) => {
    const panel = document.getElementById('results-panel') || document;
    for (const t of panel.querySelectorAll('table')) {
      const head = norm(t.querySelector('tr') ? t.querySelector('tr').textContent : '').toLowerCase();
      if (headerHas.every((h) => head.includes(h.toLowerCase()))) return t;
    }
    return null;
  };
  // tolerant oracle-row lookup: a renderer may append a BADGE to the key column
  // (e.g. "Secondary fuel filter PM" for a PM-relevant part) → exact-match fails
  // though the row is correct. Match the oracle key equal to, or a prefix of, the
  // DOM key (after stripping a trailing badge token). Keeps key parity honest.
  const lookupO = (oMap, k) => {
    if (oMap[k]) return oMap[k];
    const stripped = k.replace(/\s+(PM|✓|★|🔴|🟡|🟢)\s*$/i, '').trim();
    if (oMap[stripped]) return oMap[stripped];
    const ok = Object.keys(oMap).find((x) => k === x || k.startsWith(x + ' ') || stripped === x);
    return ok ? oMap[ok] : null;
  };

  // header-text → column index, from the table's first row.
  const headerIndex = (table) => {
    const cells = [...(table.querySelector('tr') ? table.querySelector('tr').children : [])];
    const map = {};
    cells.forEach((c, i) => { map[norm(c.textContent).toLowerCase()] = i; });
    return map;
  };

  // ── MANIFEST ────────────────────────────────────────────────────────────────
  // Each table spec: { name, headerHas[], oracle:'path.to.array', key:{header,field},
  //   cols:[{header, field, pct?, tol?}] }. A cell rendered "—" (no data) is SKIPPED
  //   (the renderer prints — when the oracle field is null), so absence isn't a defect.
  // Each scalar spec: { name, sel, oracle:(o)=>value, tol? } — headline heroes/counts.
  const MANIFEST = {
    descriptive: {
      tables: [
        { name: 'oee', headerHas: ['Machine', 'OEE'], oracle: 'oee.oee_by_asset', key: { header: 'machine', field: 'machine' },
          cols: [
            { header: 'availability', field: 'availability_pct', pct: true },   // OPERATIONAL availability (ISO 22400) — NOT the reliability one
            { header: 'quality', field: 'quality_pct', pct: true },
            { header: 'oee (partial)', field: 'oee_pct', pct: true },
          ] },
        { name: 'mtbf', headerHas: ['Machine', 'MTBF'], oracle: 'mtbf.mtbf_by_asset', key: { header: 'machine', field: 'machine' },
          cols: [ { header: 'failures', field: 'failure_count' }, { header: 'mtbf', field: 'mtbf_days', tol: 0.05 } ] },
        { name: 'mttr', headerHas: ['Machine', 'MTTR'], oracle: 'mttr.mttr_by_asset', key: { header: 'machine', field: 'machine' },
          cols: [ { header: 'repairs', field: 'repair_count' }, { header: 'total dt', field: 'total_downtime_h', tol: 0.05 }, { header: 'mttr', field: 'mttr_hours', tol: 0.05 } ] },
      ],
      scalars: [
        // summary heroes (renderAnalyticsSummary): OEE avg, worst MTBF, PM overall.
        // Oracles return NUMBERS (the runner num()-parses the "87%" / "5.6d" hero text);
        // a null → '—' hero is reported as null so an absent value isn't a false mismatch.
        { name: 'an-oee-hero', sel: '#an-oee-hero', oracle: (o) => { const a = (path(o, 'oee.oee_by_asset') || []).filter((r) => r.oee_pct != null).map((r) => +r.oee_pct); return a.length ? round(avg(a)) : null; }, tol: 0.5 },
        { name: 'an-mtbf-hero', sel: '#an-mtbf-hero', oracle: (o) => { const a = (path(o, 'mtbf.mtbf_by_asset') || []).filter((r) => r.mtbf_days != null); if (!a.length) return null; const w = a.reduce((m, r) => (r.mtbf_days < m.mtbf_days ? r : m)); return +w.mtbf_days; }, tol: 0.05 },
        { name: 'an-pm-hero', sel: '#an-pm-hero', oracle: (o) => { const p = path(o, 'pm_compliance.overall_pct'); return p == null ? null : round(p); }, tol: 0.5 },
        // OEE card header asset count
        { name: 'oee-assets-tracked', sel: null, oracle: (o) => path(o, 'oee.assets_tracked'), domText: () => { const t = findTable(['Machine', 'OEE']); const c = t && t.closest('.card'); const m = c && norm(c.textContent).match(/(\d+)\s*asset\(s\)/); return m ? m[1] : null; } },
      ],
      cardlists: [
        // Availability card renders per-asset cards (wrap:'cards') = RELIABILITY availability
        { name: 'availability-reliability', oracle: 'availability.availability_by_asset', key: 'machine', field: 'availability_pct', pct: true, cardHas: 'Availability %' },
      ],
    },
    // Other phases: precise TABLE checks (keyed parity) + cardScalars (a count
    // matched by regex INSIDE the specific card's text — robust, unlike a loose
    // page-wide number grab). Verified table structures live, 2026-06-08.
    diagnostic: {
      tables: [
        { name: 'parts-impact', headerHas: ['Machine', 'Above avg'], oracle: 'parts_availability_impact.high_downtime_jobs', key: { header: 'machine', field: 'machine' },
          cols: [ { header: 'downtime', field: 'downtime_hours', tol: 0.05 }, { header: 'above avg', field: 'above_avg_by_h', tol: 0.05 } ] },
      ],
      cardScalars: [
        { name: 'failure-mode-total', cardHas: 'Failure Mode Distribution', re: /([\d,]+)\s*total failure/i, oracle: (o) => path(o, 'failure_mode_distribution.total_failures') },
        { name: 'systemic-issues', cardHas: 'Repeat Failure Clustering', re: /(\d+)\s*systemic issue/i, oracle: (o) => path(o, 'repeat_failure_clustering.systemic_count') },
        { name: 'rcm-coverage', cardHas: 'RCM Consequence', re: /([\d.]+)%\s*cover/i, oracle: (o) => path(o, 'rcm_consequence.coverage_pct'), tol: 0.1 },
      ],
    },
    predictive: {
      tables: [
        { name: 'next-failure', headerHas: ['Machine', 'Predicted Next'], oracle: 'next_failure_dates.predictions', key: { header: 'machine', field: 'machine' },
          cols: [ { header: 'mtbf', field: 'mtbf_days', tol: 0.05 } ] },
        { name: 'parts-stockout', headerHas: ['Part', 'Stockout In'], oracle: 'parts_stockout.stockout_risk', key: { header: 'part', field: 'part_name' },
          cols: [ { header: 'in stock', field: 'qty_on_hand' }, { header: 'daily rate', field: 'daily_rate', tol: 0.01 } ] },
        // anomaly_baseline table is keyed machine×reading (87 rows, key collisions) → row-count only, no cell parity.
      ],
      cardScalars: [
        { name: 'anomaly-machines', cardHas: 'Anomaly Baseline', re: /(\d+)\s*machine\(s\)/i, oracle: (o) => path(o, 'anomaly_baseline.machines_tracked') },
        { name: 'stockout-at-risk', cardHas: 'Parts Stockout', re: /(\d+)\s*parts? at risk/i, oracle: (o) => path(o, 'parts_stockout.at_risk_count') },
      ],
    },
    prescriptive: {
      tables: [
        { name: 'priority', headerHas: ['Priority', 'Score'], oracle: 'priority_ranking.ranking', key: { header: 'machine', field: 'machine' },
          cols: [ { header: 'failures', field: 'failure_count' }, { header: 'avg dt', field: 'avg_downtime_h', tol: 0.05 }, { header: 'score', field: 'risk_score', tol: 0.1 } ] },
        { name: 'parts-reorder', headerHas: ['Part', 'Reorder At'], oracle: 'parts_reorder.reorder', key: { header: 'part', field: 'part_name' },
          cols: [ { header: 'in stock', field: 'qty_on_hand' }, { header: 'reorder at', field: 'reorder_point' } ] },
      ],
      cardScalars: [
        { name: 'priority-p1', cardHas: 'Priority Maintenance Ranking', re: /(\d+)\s*P1/i, oracle: (o) => path(o, 'priority_ranking.p1_count') },
        { name: 'priority-p2', cardHas: 'Priority Maintenance Ranking', re: /(\d+)\s*P2/i, oracle: (o) => path(o, 'priority_ranking.p2_count') },
        { name: 'reorder-critical', cardHas: 'Parts Reorder', re: /(\d+)\s*critical/i, oracle: (o) => path(o, 'parts_reorder.critical_count') },
        { name: 'open-jobs', cardHas: 'Technician Assignment', re: /(\d+)\s*open job/i, oracle: (o) => path(o, 'technician_assignment.open_job_count') },
        { name: 'pm-interval-count', cardHas: 'PM Interval Optimization', re: /(\d+)\s*recommendati/i, oracle: (o) => path(o, 'pm_interval_optimization.count') },
      ],
    },
  };

  // ── build the parity[] for a phase from the live oracle + rendered DOM ───────
  function build(phase, oracle) {
    const spec = MANIFEST[phase] || {};
    const parity = []; const notes = [];

    // tables → one parity entry per column (keyed map dom vs oracle)
    for (const t of (spec.tables || [])) {
      const table = findTable(t.headerHas);
      if (!table) { if (!t.optional) notes.push(`table '${t.name}' not found (headers ${t.headerHas})`); continue; }
      const hidx = headerIndex(table);
      const keyCol = hidx[t.key.header];
      const rows = [...table.querySelectorAll('tr')].slice(1);
      const oracleArr = path(oracle, t.oracle) || [];
      const oMap = {}; oracleArr.forEach((r) => { oMap[norm(r[t.key.field])] = r; });
      for (const col of t.cols) {
        const ci = hidx[col.header];
        if (ci == null) { notes.push(`col '${col.header}' missing in '${t.name}'`); continue; }
        const dom = {}; const ora = {};
        for (const tr of rows) {
          const cells = tr.children; if (!cells || cells.length <= Math.max(keyCol, ci)) continue;
          const k = norm(cells[keyCol].textContent); if (!k) continue;
          const raw = norm(cells[ci].textContent);
          if (raw === '—' || raw === '') continue;                 // renderer prints — for null oracle → skip
          dom[k] = col.pct || /[\d.]/.test(raw) ? num(raw) : raw;
          const orow = lookupO(oMap, k); if (orow) ora[k] = orow[col.field];
        }
        parity.push({ name: `${phase}:${t.name}.${col.field}`, dom, oracle: ora, tol: col.tol == null ? 0.1 : col.tol });
      }
    }

    // cardlists → keyed map from per-asset cards
    for (const cl of (spec.cardlists || [])) {
      const card = [...document.querySelectorAll('.card')].find((c) => norm(c.textContent).includes(cl.cardHas));
      const oracleArr = path(oracle, cl.oracle) || [];
      if (card) {
        const dom = {}; const ora = {};
        // each per-asset row inside the card: a label (asset) + a "NN%" value
        const txt = norm(card.textContent);
        oracleArr.forEach((r) => {
          const k = norm(r[cl.key]);
          const re = new RegExp(k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[^%]*?(\\d+(?:\\.\\d+)?)%');
          const m = txt.match(re);
          if (m && r[cl.field] != null) { dom[k] = num(m[1]); ora[k] = r[cl.field]; }
        });
        if (Object.keys(dom).length) parity.push({ name: `${phase}:${cl.name}`, dom, oracle: ora, tol: cl.pct ? 0.6 : 0.1 });
        else notes.push(`cardlist '${cl.name}': matched 0 of ${oracleArr.length} (selector/format?)`);
      } else notes.push(`cardlist '${cl.name}' card not found ('${cl.cardHas}')`);
    }

    // scalars → single dom vs oracle
    for (const s of (spec.scalars || [])) {
      let domVal = null;
      if (s.sel) { const el = document.querySelector(s.sel); domVal = el ? norm(el.textContent) : null; }
      else if (s.domText) { try { domVal = s.domText(); } catch (_) { domVal = null; } }
      else if (s.domNear) { domVal = nearNumber(s.domNear); }
      const oracleVal = s.oracle(oracle);
      if (domVal == null) { notes.push(`scalar '${s.name}': DOM value not located`); continue; }
      const dv = (typeof oracleVal === 'number' || /^\s*-?\d/.test(String(domVal))) ? num(domVal) : norm(domVal);
      parity.push({ name: `${phase}:scalar.${s.name}`, dom: dv, oracle: oracleVal, tol: s.tol == null ? 0.5 : s.tol });
    }

    // cardScalars → a count matched by regex INSIDE a specific card's text
    // (scoped → robust). e.g. "🔴 4 P1" in the Priority Ranking card == p1_count.
    for (const cs of (spec.cardScalars || [])) {
      const card = [...document.querySelectorAll('.card')].find((c) => norm(c.textContent).includes(cs.cardHas));
      if (!card) { notes.push(`cardScalar '${cs.name}': card '${cs.cardHas}' not found`); continue; }
      const m = norm(card.textContent).match(cs.re);
      const oracleVal = cs.oracle(oracle);
      if (!m) { notes.push(`cardScalar '${cs.name}': pattern ${cs.re} not in card`); continue; }
      parity.push({ name: `${phase}:card.${cs.name}`, dom: num(m[1]), oracle: oracleVal == null ? oracleVal : (typeof oracleVal === 'number' ? oracleVal : num(oracleVal)), tol: cs.tol == null ? 0.5 : cs.tol });
    }

    return { phase, parity, notes, _v: V };
  }

  // find a number rendered next to one of `labels` (loose, for count tiles).
  function nearNumber(labels) {
    const panel = document.getElementById('results-panel') || document.body;
    const els = [...panel.querySelectorAll('*')].filter((e) => e.children.length === 0);
    for (const lab of labels) {
      for (const e of els) {
        const t = norm(e.textContent).toLowerCase();
        if (t === lab || t.includes(lab)) {
          // look at siblings / parent for a bare number
          const around = norm((e.parentElement || e).textContent);
          const m = around.match(/-?\d+(?:\.\d+)?/);
          if (m) return m[0];
        }
      }
    }
    return null;
  }

  window.__ANALYTICS_PARITY = { _v: V, build, MANIFEST, _findTable: findTable, _nearNumber: nearNumber };
  return { installed: true, _v: V, phases: Object.keys(MANIFEST), hint: 'spec = __ANALYTICS_PARITY.build(phase, oracle) → __UFAI.run({parity: spec.parity})' };
}
