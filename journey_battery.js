/* ============================================================================
 * journey_battery.js — ③ JOURNEY battery  (v0.1.0)
 * ============================================================================
 * The altitude ABOVE the page: can a user COMPLETE a job-to-be-done that spans
 * several pages? The page battery (ufai_battery.js) sees one screen; this asserts
 * the two things only a JOURNEY can check, and that a single-page run is blind to:
 *
 *   1. STATE CONTINUITY  — identity (hive/role/worker) and any carried selection
 *      persist across the navigations of the flow (no silent re-auth, no dropped
 *      context).
 *   2. NUMBER CONTINUITY  — the SAME named KPI shows the SAME value at every step
 *      it appears. A disagreement is the executable proof of the cross-page
 *      derivation drift the IA Phase-3 walkthrough flagged (e.g. "overdue" derived
 *      two ways on pm-scheduler vs dayplanner) — the redundancy that CAUSES
 *      what-bugs, caught live.
 *
 * WHY sessionStorage: a journey crosses page loads, so page-JS state can't carry.
 * Steps are journaled in sessionStorage (survives same-tab navigation); install
 * this on EVERY page (idempotent), call step() after each page renders, then
 * verdict() at the end. It is the JOURNEY-altitude driver in BATTERY_ARCHITECTURE.md
 * — it composes, not replaces, the page kernel (run __UFAI per page as usual).
 *
 * USAGE (driven from Playwright MCP across a flow):
 *   // page A:
 *   browser_evaluate(fn = <this file>)                                  // install
 *   browser_evaluate("()=>window.__JOURNEY.reset()")                    // start fresh
 *   browser_evaluate("()=>window.__JOURNEY.step('pm-scheduler', {overdue:'[data-rag-tile=\"pm-scheduler:overdue\"] .sc-hero'})")
 *   // navigate to page B, re-install, then:
 *   browser_evaluate("()=>window.__JOURNEY.step('dayplanner', {overdue:'[data-rag-tile=\"dayplanner:overdue_count\"] .sc-hero'})")
 *   // at the end:
 *   browser_evaluate("()=>window.__JOURNEY.verdict({tol:0.5})")         // → defects[]
 *
 * DOCTRINE: SURFACES drift; fixes nothing. A number-continuity miss is a Major
 * candidate (it can hide a stale value) but VERIFY-FIRST: same-NAMED ≠ same-
 * DERIVATION — confirm both steps mean the SAME metric before calling it a bug.
 * ==========================================================================*/
() => {
  const V = '0.2.0';
  if (window.__JOURNEY && window.__JOURNEY._v === V) return { already: true, _v: V };
  const KEY = '__journey_steps_v1';

  const norm = (s) => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
  const round = (n, d = 2) => (n == null ? null : Math.round(n * 10 ** d) / 10 ** d);
  const numOrText = (s) => {
    if (s == null) return null;
    const m = String(s).replace(/[, ]/g, '').match(/-?\d+(?:\.\d+)?/);
    return m ? parseFloat(m[0]) : norm(s);
  };
  const load = () => { try { return JSON.parse(sessionStorage.getItem(KEY) || '[]'); } catch (_) { return []; } };
  const save = (s) => { try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch (_) { /* quota */ } };

  const identity = () => {
    if (window.WHShell) {
      try { return { mode: window.WHShell.mode(), role: window.WHShell.role(), hive: window.WHShell.hiveId() ? '(set)' : '(none)' }; } catch (_) { /* */ }
    }
    return { note: 'no WHShell seam' };
  };

  function reset() { save([]); return { ok: true, cleared: true }; }

  // record one step: read each named KPI from the current page.
  // kpis = { name: cssSelector | number }. A selector reads .textContent → number.
  function step(label, kpis = {}) {
    const readings = {};
    for (const [name, spec] of Object.entries(kpis)) {
      if (typeof spec === 'number') { readings[name] = spec; continue; }
      let el = null; try { el = document.querySelector(spec); } catch (_) { /* bad sel */ }
      readings[name] = el ? numOrText(el.textContent) : null;
    }
    const steps = load();
    steps.push({ label, url: location.pathname.split('/').pop() || location.pathname, ts: Date.now(), readings, identity: identity() });
    save(steps);
    return { step: steps.length, label, readings, identity: steps[steps.length - 1].identity };
  }

  function verdict(opts = {}) {
    const tol = opts.tol == null ? 0.5 : opts.tol;
    const steps = load();
    const defects = [];
    const D = (check, measured, expected, fixHint, severity = 'Major') => ({ pillar: 'C', check, severity, measured, expected, fixHint });

    // ── STATE continuity — identity must not change mid-journey ──────────────
    const ids = steps.map((s) => s.identity).filter((x) => x && !x.note);
    for (let i = 1; i < ids.length; i++) {
      for (const k of ['mode', 'role', 'hive']) {
        if (ids[i][k] !== ids[i - 1][k]) {
          defects.push(D('journey-state-lost',
            `${k} changed ${ids[i - 1][k]} → ${ids[i][k]} between "${steps[i - 1].label}" and "${steps[i].label}"`,
            `${k} constant across the journey`,
            'identity/context dropped mid-flow — a silent re-auth or lost selection breaks the task', 'Major'));
        }
      }
    }

    // ── NUMBER continuity — same named KPI must agree at every step ───────────
    const byName = {};
    steps.forEach((s) => { for (const [n, v] of Object.entries(s.readings || {})) { (byName[n] = byName[n] || []).push({ label: s.label, v }); } });
    const checks = [];
    for (const [name, arr] of Object.entries(byName)) {
      const nums = arr.filter((a) => typeof a.v === 'number').map((a) => a.v);
      const present = arr.filter((a) => a.v != null);
      if (present.length < 2) { checks.push({ name, status: 'single-step', seen: arr }); continue; }
      if (nums.length >= 2) {
        const min = Math.min(...nums), max = Math.max(...nums);
        const agree = (max - min) <= tol;
        checks.push({ name, status: agree ? 'agree' : 'DRIFT', min, max, seen: arr });
        if (!agree) defects.push(D('journey-number-drift',
          `${name}: ${arr.map((a) => a.label + '=' + a.v).join(' | ')} (spread ${round(max - min)})`,
          `same ${name} at every step (±${tol})`,
          'VERIFY-FIRST same-named≠same-derivation; if it IS one metric, this cross-page disagreement is a drift bug that can show users a stale value', 'Major'));
      } else {
        const vals = present.map((a) => String(a.v));
        const agree = new Set(vals).size === 1;
        checks.push({ name, status: agree ? 'agree' : 'DRIFT', seen: arr });
        if (!agree) defects.push(D('journey-text-drift',
          `${name}: ${arr.map((a) => a.label + '="' + a.v + '"').join(' | ')}`,
          `same ${name} text at every step`, 'a label/status that changes across the flow for the same entity — verify the binding', 'Minor'));
      }
    }

    // ── ACTION outcomes (Gap 3) — a recorded assertEqual that FAILED is a real
    // task bug: a control and the data it drives disagree (e.g. a tab labeled
    // "Overdue (2)" that renders a different number of rows). An action that
    // THREW means the job is blocked.
    for (const s of steps.filter((x) => x.assert)) {
      if (!s.assert.ok) defects.push(D('journey-action-inconsistency',
        `"${s.label}": ${s.assert.aSpec}=${s.assert.a} ≠ ${s.assert.bSpec}=${s.assert.b}`,
        `${s.assert.aSpec} == ${s.assert.bSpec} after the action`,
        'a control and the data it drives disagree — the user acts and the result contradicts the number they tapped', 'Major'));
    }
    for (const s of steps.filter((x) => x.action && x.error)) defects.push(D('journey-action-error',
      `"${s.label}" threw: ${s.error}`, 'the action completes',
      'the journey could not perform its action — the task is blocked for the user', 'Major'));

    return {
      battery: 'JOURNEY v' + V, steps: steps.length,
      path: steps.map((s) => s.label + (s.action ? ' ⚡' : s.assert ? ' ✓?' : '')),
      identity: steps.map((s) => s.identity),
      continuity: checks,
      actions: steps.filter((s) => s.action || s.assert).map((s) => s.action ? { act: s.label, error: s.error || null } : { assert: s.label, ...s.assert }),
      defects, major: defects.filter((d) => d.severity === 'Major').length,
      complete: steps.length >= 2,
      note: steps.length < 2 ? 'a journey needs ≥2 steps to assert continuity' : 'journey continuity + action verdict',
    };
  }

  // ── Gap 3: ACTION-journey — DO the job, not just read it. act() performs an
  // interaction (fill/click) then snapshots; assertEqual() checks that a control
  // and the data it drives agree (the consistency a read-only journey can't see).
  async function act(label, fn) {
    let error = null;
    try { await fn(); } catch (e) { error = String(e && e.message || e); }
    await new Promise((r) => setTimeout(r, 500));   // let the render settle
    const steps = load();
    steps.push({ label, url: location.pathname.split('/').pop() || location.pathname, ts: Date.now(), action: true, error, identity: identity() });
    save(steps);
    return { step: steps.length, label, action: true, error };
  }

  // assert two live readings are equal. A spec is a number, a CSS selector
  // (reads .textContent → number), or { count: selector } (counts matches).
  function assertEqual(label, aSpec, bSpec, opts = {}) {
    const tol = opts.tol == null ? 0 : opts.tol;
    const readOne = (spec) => {
      if (typeof spec === 'number') return spec;
      if (spec && spec.count != null) { try { return document.querySelectorAll(spec.count).length; } catch (_) { return null; } }
      let el = null; try { el = document.querySelector(spec); } catch (_) { /* */ }
      return el ? numOrText(el.textContent) : null;
    };
    const a = readOne(aSpec), b = readOne(bSpec);
    const ok = (typeof a === 'number' && typeof b === 'number') ? Math.abs(a - b) <= tol : a === b;
    const steps = load();
    steps.push({ label, url: location.pathname.split('/').pop() || location.pathname, ts: Date.now(),
      assert: { a, b, ok, aSpec: String((aSpec && aSpec.count) || aSpec), bSpec: String((bSpec && bSpec.count) || bSpec) }, identity: identity() });
    save(steps);
    return { step: steps.length, label, a, b, ok };
  }

  window.__JOURNEY = { _v: V, reset, step, act, assertEqual, verdict, _load: load };
  return { installed: true, _v: V, hint: 'reset() → step(label,{kpi:sel}) | act(label,fn) | assertEqual(label,kpiSel,{count:rowSel}) → verdict({tol})' };
}
