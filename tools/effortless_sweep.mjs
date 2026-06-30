// effortless_sweep.mjs — Arc V (EFFORTLESS): the friction meter.
//
// Reuses the Arc-K recipe (signIn / makeHelpers / config — imported, ONE source of truth, no
// drift) and re-drives the SAME registered JTBDs with COUNTED helpers, so we measure the
// interaction cost (clicks + page-hops) of every job WITHOUT touching a single drive().
//
// R0 (this slice) = the EFFORT lens + a FLOW seed. Emits arc_v_results.json and ratchets
// arc_v_baseline.json: the whole-platform total click-hops is a CEILING (forward-only — any
// new friction fails the gate), plus excess-click DEBT vs seeded ideals.
//
// USAGE:
//   node tools/effortless_sweep.mjs                  # all local journeys
//   node tools/effortless_sweep.mjs --page index.html
//   node tools/effortless_sweep.mjs --phase K1
//   node tools/effortless_sweep.mjs --accept         # forward-only cost ratchet
//   node tools/effortless_sweep.mjs --accept --update-baseline

import { chromium } from 'playwright';
import { writeFileSync, readFileSync, existsSync } from 'fs';
import { JOURNEYS } from './live_page_journeys.registry.mjs';
import { signIn, makeHelpers, ACCOUNTS, SEEDER, HIVE } from './live_page_journeys.mjs';
import { instrumentHelpers, scoreEffort, rollupEffort, IDEAL, LOAD_PROBE, scoreLoad, CLARITY_PROBE, scoreClarity } from './live_page_journeys.effort.mjs';

const args = process.argv.slice(2);
const HEADED = args.includes('--headed');
const ACCEPT = args.includes('--accept');
const UPDATE_BASELINE = args.includes('--update-baseline');
const PHASE_ONLY = (() => { const i = args.indexOf('--phase'); return i >= 0 ? args[i + 1] : null; })();
const PAGE_ONLY = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const RESULTS = 'arc_v_results.json';
const BASELINE = 'arc_v_baseline.json';
const TOL = 2; // small tolerance: a few drives branch on seeded state, so total click-hops can
               // jitter by 1-2 run-to-run. R0 ratchets the TOTAL; per-page debt gets sharp teeth
               // as each sub-arc seeds ideals.

(async () => {
  // external-ceiling journeys (◈, e.g. IN5 CMMS) hit real external APIs — skip from the LOCAL
  // friction sweep entirely (Arc K excludes them from its % too).
  let journeys = JOURNEYS.filter(j => !j.external
    && (!PHASE_ONLY || j.phase === PHASE_ONLY)
    && (!PAGE_ONLY || j.page === PAGE_ONLY));
  if (!journeys.length) { console.error(`[V] no journeys match (phase=${PHASE_ONLY} page=${PAGE_ONLY}). Registered: ${JOURNEYS.length}`); process.exit(2); }

  const browser = await chromium.launch({ headless: !HEADED });
  const rolesNeeded = [...new Set(journeys.map(j => j.role))];
  const contexts = {};
  for (const role of rolesNeeded) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'Asia/Manila' });
    const si = await signIn(ctx, role);
    console.log(`[V] sign-in ${role.padEnd(11)}: ${si.ok ? (si.anon ? 'ANON (no session)' : 'OK') : 'FAIL ' + si.err}`);
    contexts[role] = ctx;
  }

  const records = [];
  for (const j of journeys) {
    const page = await contexts[j.role].newPage();
    const base = makeHelpers(page);
    const { helpers, counters } = instrumentHelpers(base);
    let err = null;
    try { await j.drive(page, helpers); }
    catch (e) { err = String(e).slice(0, 200); }
    await page.close();
    const effort = scoreEffort(counters, IDEAL[j.id]);
    records.push({ id: j.id, phase: j.phase, page: j.page, role: j.role, title: j.title, effort, err });
    const dbt = effort.pass === false ? ` debt=${effort.debt}` : '';
    console.log(`  ${(j.id + ' ' + j.role).padEnd(22)} ${j.page.padEnd(22)} clicks=${String(effort.clicks).padStart(2)} hops=${String(effort.hops).padStart(2)} cost=${String(effort.click_hops).padStart(2)}${effort.slow_actions ? ' slow=' + effort.slow_actions : ''}${dbt}${err ? '  ERR ' + err : ''}`);
  }

  // ── L lens (Load / cognitive density) — probe each unique page once at the MOBILE viewport
  //    (390px = where density bites a gloved field worker), using its primary role's context. ──
  const pageRole = {};
  for (const j of journeys) { if (!pageRole[j.page]) pageRole[j.page] = j.role; }
  const loadByPage = {};
  const clarityByPage = {};
  for (const [pg, role] of Object.entries(pageRole)) {
    const ctx = contexts[role] || contexts[journeys[0].role];
    if (!ctx) continue;
    const page = await ctx.newPage();
    try {
      await page.goto(`${SEEDER}/workhive/${pg}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.setViewportSize({ width: 390, height: 780 });
      await page.waitForTimeout(2000);
      loadByPage[pg] = scoreLoad(await page.evaluate(LOAD_PROBE));        // L lens (gated)
      clarityByPage[pg] = scoreClarity(await page.evaluate(CLARITY_PROBE)); // C lens (informational v1)
    } catch (e) { loadByPage[pg] = { __err: String(e).slice(0, 100) }; clarityByPage[pg] = { __err: true }; }
    await page.close();
  }

  for (const c of Object.values(contexts)) await c.close();
  await browser.close();

  const roll = rollupEffort(records);
  const out = { ran: new Date().toISOString(), seeder: SEEDER, hive: HIVE, summary: roll, journeys: records };

  // ── per-page interaction-cost rollup (the per-arc lens) ──
  const perPage = {};
  for (const r of records) {
    if (r.err) continue;
    const p = (perPage[r.page] = perPage[r.page] || { page: r.page, journeys: 0, click_hops: 0, debt: 0, slow: 0, slow_silent: 0, dead_ends: 0, flow_floor: 0 });
    p.journeys++; p.click_hops += r.effort.click_hops; p.debt += r.effort.debt; p.slow += r.effort.slow_actions;
    const f = r.effort.flow || {}; p.slow_silent += f.slow_silent || 0; p.dead_ends += f.dead_ends || 0; p.flow_floor += f.flow_floor || 0;
  }
  for (const p of Object.values(perPage)) {
    const l = loadByPage[p.page]; if (l && !l.__err) { p.density = l.density; p.max_choices = l.max_choices; p.miller = l.miller_violations; p.load_floor = l.load_floor; }
    const c = clarityByPage[p.page]; if (c && !c.__err) { p.vague_ctas = c.vague_ctas; p.icon_only = c.icon_only_unlabeled; p.competing_primary = c.competing_primary; p.clarity_signal = c.clarity_signal; }
  }
  out.per_page = Object.values(perPage).sort((a, b) => b.click_hops - a.click_hops);
  const loadVals = Object.values(loadByPage).filter(l => l && !l.__err);
  out.load = {
    pages_probed: loadVals.length,
    total_load_floor: loadVals.reduce((s, l) => s + (l.load_floor || 0), 0),
    miller_violations: loadVals.reduce((s, l) => s + (l.miller_violations || 0), 0),
    dense_pages: loadVals.filter(l => l.dense_screen).length,
    by_page: loadByPage,
  };
  // ── F lens (Flow / Doherty) — slow-and-silent + dead-ends, rolled to a ratchetable floor ──
  out.flow = {
    total_flow_floor: roll.total_flow_floor,       // the gated F-floor (→ 0)
    total_slow_silent: roll.total_slow_silent,     // slow + no busy affordance
    total_dead_ends: roll.total_dead_ends,         // interactive action that failed
    total_slow_with_busy: roll.total_slow_with_busy, // slow but WITH feedback = Doherty-OK (informational)
  };
  // ── C lens (Clarity / Jakob) — INFORMATIONAL v1 (not gated until a discriminating signal calibrates) ──
  const clarityVals = Object.values(clarityByPage).filter(c => c && !c.__err);
  out.clarity = {
    pages_probed: clarityVals.length,
    total_clarity_signal: clarityVals.reduce((s, c) => s + (c.clarity_signal || 0), 0), // vague + unlabeled
    total_vague_ctas: clarityVals.reduce((s, c) => s + (c.vague_ctas || 0), 0),
    total_icon_only_unlabeled: clarityVals.reduce((s, c) => s + (c.icon_only_unlabeled || 0), 0),
    pages_competing_primary: clarityVals.filter(c => (c.competing_primary || 0) > 1).length,
    by_page: clarityByPage,
  };

  console.log('\n' + '='.repeat(70));
  console.log('ARC V — EFFORTLESS (interaction-cost / friction meter)');
  console.log('='.repeat(70));
  console.log(`  journeys measured : ${roll.measured}/${roll.journeys} (${roll.errored} errored)`);
  console.log(`  TOTAL click-hops  : ${roll.total_click_hops}  (the platform interaction-cost ceiling)`);
  console.log(`  total steps       : ${roll.total_steps}  (clicks+hops+fills)`);
  console.log(`  excess-click DEBT : ${roll.total_debt}  (vs ${roll.journeys_with_ideal} seeded ideals)  ${roll.effort_pct != null ? '· effort ' + roll.effort_pct + '%' : ''}`);
  console.log(`  slow actions      : ${roll.total_slow_actions} (>400ms Doherty · F-lens seed)  · failed: ${roll.total_failed_actions}`);
  console.log(`\n  heaviest pages (click-hops):`);
  for (const p of out.per_page.slice(0, 12)) console.log(`    ${p.page.padEnd(26)} ${String(p.click_hops).padStart(3)} cost · ${p.journeys}j${p.debt ? ' · debt ' + p.debt : ''}${p.slow ? ' · slow ' + p.slow : ''}`);
  console.log(`\n  L-lens (Load): ${out.load.total_load_floor} load-floor · ${out.load.miller_violations} Miller(>7-choice) · ${out.load.dense_pages} walls (>40 above-fold) · ${out.load.pages_probed} pages probed`);
  const denseP = out.per_page.filter(p => p.density != null).sort((a, b) => (b.density || 0) - (a.density || 0));
  for (const p of denseP.slice(0, 8)) console.log(`    ${p.page.padEnd(26)} density ${String(p.density).padStart(3)} · maxChoices ${p.max_choices}${p.miller ? ' · Miller ' + p.miller : ''}${p.load_floor ? ' · load-floor ' + p.load_floor : ''}`);
  console.log(`\n  F-lens (Flow/Doherty): ${out.flow.total_flow_floor} flow-floor = ${out.flow.total_dead_ends} dead-ends (GATED: failed clicks/fills = user stuck)  · ${out.flow.total_slow_silent} slow-silent (INFO: >400ms no busy affordance = fix targets) · ${out.flow.total_slow_with_busy} slow-but-busy (Doherty-OK)`);
  const flowP = out.per_page.filter(p => (p.flow_floor || 0) > 0 || (p.slow_silent || 0) > 0).sort((a, b) => ((b.flow_floor || 0) + (b.slow_silent || 0)) - ((a.flow_floor || 0) + (a.slow_silent || 0)));
  for (const p of flowP.slice(0, 8)) console.log(`    ${p.page.padEnd(26)} dead-ends ${String(p.dead_ends || 0).padStart(2)} (gated) · slow-silent ${p.slow_silent || 0} (info)`);
  console.log(`\n  C-lens (Clarity/Jakob, INFORMATIONAL v1): ${out.clarity.total_clarity_signal} clarity-signal = ${out.clarity.total_vague_ctas} vague-CTAs + ${out.clarity.total_icon_only_unlabeled} icon-only-unlabeled · ${out.clarity.pages_competing_primary} pages w/ competing primaries · ${out.clarity.pages_probed} probed`);
  const clarP = out.per_page.filter(p => (p.clarity_signal || 0) > 0).sort((a, b) => (b.clarity_signal || 0) - (a.clarity_signal || 0));
  for (const p of clarP.slice(0, 8)) console.log(`    ${p.page.padEnd(26)} clarity-signal ${String(p.clarity_signal).padStart(2)} · vague ${p.vague_ctas || 0} · icon-only ${p.icon_only || 0}${(p.competing_primary || 0) > 1 ? ' · competing-primary ' + p.competing_primary : ''}`);

  // ── forward-only ratchet: total click-hops is a CEILING (cost must not rise) + debt≤baseline ──
  if (ACCEPT) {
    const cur = { total_click_hops: roll.total_click_hops, total_debt: roll.total_debt, total_load_floor: out.load.total_load_floor, total_flow_floor: out.flow.total_flow_floor, measured: roll.measured };
    if (UPDATE_BASELINE || !existsSync(BASELINE)) {
      writeFileSync(BASELINE, JSON.stringify({ ...cur, tol: TOL, set: new Date().toISOString() }, null, 2));
      console.log(`\n[V] baseline ${UPDATE_BASELINE ? 'UPDATED' : 'created'}: click_hops<=${cur.total_click_hops} (+${TOL} tol), debt<=${cur.total_debt}, load-floor<=${cur.total_load_floor}, flow-floor<=${cur.total_flow_floor}`);
    } else {
      const b = JSON.parse(readFileSync(BASELINE, 'utf8'));
      let failed = false;
      if (roll.total_click_hops > b.total_click_hops + (b.tol ?? TOL)) { console.error(`\n[V] RATCHET FAIL: click_hops ${roll.total_click_hops} > baseline ${b.total_click_hops} (+${b.tol ?? TOL} tol)`); failed = true; }
      if (b.total_debt != null && roll.total_debt > b.total_debt) { console.error(`[V] RATCHET FAIL: excess-click debt ${roll.total_debt} > baseline ${b.total_debt}`); failed = true; }
      if (b.total_load_floor != null && out.load.total_load_floor > b.total_load_floor) { console.error(`[V] RATCHET FAIL: cognitive-load floor ${out.load.total_load_floor} > baseline ${b.total_load_floor}`); failed = true; }
      if (b.total_flow_floor != null && out.flow.total_flow_floor > b.total_flow_floor + (b.tol ?? TOL)) { console.error(`[V] RATCHET FAIL: flow floor ${out.flow.total_flow_floor} > baseline ${b.total_flow_floor} (+${b.tol ?? TOL} tol)`); failed = true; }
      if (failed) { writeFileSync(RESULTS, JSON.stringify(out, null, 2)); process.exit(1); }
      console.log(`\n[V] ratchet OK: click_hops ${roll.total_click_hops}<=${b.total_click_hops}(+${b.tol ?? TOL}), debt ${roll.total_debt}<=${b.total_debt}, load-floor ${out.load.total_load_floor}<=${b.total_load_floor}, flow-floor ${out.flow.total_flow_floor}<=${b.total_flow_floor}(+${b.tol ?? TOL})`);
    }
  }

  writeFileSync(RESULTS, JSON.stringify(out, null, 2));
  console.log(`\n  -> wrote ${RESULTS} (${records.length} journeys)`);
})();
