// prove_hive_startup.mjs - BRH-H + BRH-G (2026-10-15): the stored hive and its name are caches of server facts, and a
// page that scopes by them settles them in its OWN start-up.
//
// WHY. Ian's six hive assets vanished from the logbook because the stored hive had been wiped, and only the home ever
// refilled it. whHiveRecovery (utils.js) now re-seats it on every page - but AFTER load: the page has already rendered
// solo (the wrong answer as the default), and anything done in that window is done in solo mode, until one reload puts
// it right (class H, 25 pages). Its twin: a hive renamed on another device stays under its old name on every page that
// paints localStorage wh_hive_name and never asks the server (class G, 17 pages).
//
// Per page, at 390 AND 1280, as the row's cast (a returner: Bryan Garcia, a worker of Baguio Textile Mills), signed in
// through the product's own client, in a fresh context:
//   H  the stored hive WIPED (wh_active_hive_id, wh_hive_id, wh_hive_name, wh_hive_role, wh_hives): the page must seat
//      it in its start-up - ONE document load, no recovery reload (sessionStorage wh_hive_recovered never set), the
//      device's hive his at the end.
//   G  the stored name STALE ("Old Plant Name"): once the page settles, the stale name is shown nowhere and the stored
//      name is the hive's real one.
//
//   node tools/prove_hive_startup.mjs [--page a.html,b.html] [--viewport 390] [--class H|G] [--json out.json]
//        [--before]   the reproduction: every row's page must FAIL its reading before the fix
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { SEEDER, HIVE, signIn, stubModelCalls, PAGE_QUERY, psql } from './prover_harness.mjs';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const OUT = arg('--json', '.tmp/hive_startup_results.json');
const BEFORE = process.argv.includes('--before');
const ONLY = arg('--class');
const VPS = (arg('--viewport') ? [Number(arg('--viewport'))] : [390, 1280]).map((w) => [w, w === 390 ? 844 : 800]);
const STALE = 'Old Plant Name';
// G pages that do NOT show the hive name on load - each reads the stored name only at the moment of use, after utils.js
// has reconciled it (asset-hub and integrations: the CSV export's "Scope"/"Hive" line; report-sender: the lost-context
// notice). Their rows record "no stale name, because none is shown"; every OTHER G page must show the REAL name, the
// positive control that keeps a page which simply failed to render from passing as "no stale name on screen".
const USE_TIME = new Set(['asset-hub.html', 'integrations.html', 'report-sender.html']);
const WIPE = ['wh_active_hive_id', 'wh_hive_id', 'wh_hive_name', 'wh_hive_role', 'wh_hives'];

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const rows = reg.trajectories.filter((t) => t.brh && ['H', 'G'].includes(t.brh.cls) && t.status !== 'descoped'
  && (!ONLY || t.brh.cls === ONLY));
const wanted = arg('--page') ? new Set(arg('--page').split(',')) : null;
const ROSTER = rows.filter((t) => !wanted || wanted.has(t.brh.page)).map((t) => ({ id: t.id, cls: t.brh.cls, page: t.brh.page }));
const ACCTS = {
  bryan: { name: 'Bryan Garcia', first: 'Bryan', role: 'worker', email: 'bryangarcia@auth.workhiveph.com', password: 'test1234' },
  leandro: { name: 'Leandro Marquez', first: 'Leandro', role: 'supervisor', email: 'leandromarquez@auth.workhiveph.com', password: 'test1234' },
};
// a G row can only be read by someone the page ADMITS: a supervisors-only page shows a worker its refusal, never the
// hive's name, so its returner is the hive's supervisor (WH_PAGE_GATES - the pages' own measured gates)
const GATED = new Set([...(readFileSync('utils.js', 'utf8').match(/var WH_PAGE_GATES = \{([\s\S]*?)\};/) || ['', ''])[1]
  .matchAll(/'([a-z0-9-]+\.html)':/g)].map((m) => m[1]));
const acctFor = (row) => ((row.cls === 'G' && GATED.has(row.page)) || row.admitted) ? 'leandro' : 'bryan';
// on a page that refuses some people, the wipe takes the stored ROLE with the hive: an ADMITTED person is read too, and
// must not be refused once the seat has brought the membership's role back (the head's pre-paint and the role gates
// read the stored role - a wiped one would wall a supervisor out of their own console)
const REFUSED_RX = /Supervisor access only|Supervisors only|Platform Admins Only|for platform admins only|Founder access only/i;
// a page that shows the name only on a document it opens (project-report's cover) is opened ON one: the hive's newest project
const PROJECT = psql(`select id from projects where hive_id = '${HIVE}' order by created_at desc limit 1`);
const ROW_QUERY = { 'project-report.html': PROJECT ? `?project_id=${PROJECT}` : '' };

const BROWSER = await chromium.launch();
const STATES = {};
let REAL = null;
for (const [k, acct] of Object.entries(ACCTS)) {
  const ctx = await BROWSER.newContext({ serviceWorkers: 'block' });
  if (await signIn(ctx, { ...acct, hive: HIVE })) {
    const p = await ctx.newPage();
    await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
    await p.waitForTimeout(2500);
    REAL = REAL || await p.evaluate(() => localStorage.getItem('wh_hive_name'));
    STATES[k] = await ctx.storageState();
  }
  await ctx.close();
}
if (!STATES.bryan || !STATES.leandro || !REAL) { console.log(`FAIL hive-startup - sign-in or the hive's real name failed (name=${REAL})`); process.exit(1); }

async function read(row, [w, h]) {
  const who = acctFor(row);
  const ctx = await BROWSER.newContext({ serviceWorkers: 'block', storageState: STATES[who] });
  await stubModelCalls(ctx);
  await ctx.route('**/functions/v1/**', (r) => r.request().method() === 'OPTIONS' ? r.fallback()
    : r.fallback({ headers: { ...r.request().headers(), 'x-wh-walk-no-model': '1' } }));
  // the device state is written BEFORE any page script runs, on every document of this context
  await ctx.addInitScript(([cls, wipe, stale, baseline]) => {
    try {
      if (baseline) return;                                     // the device as it normally is: the comparison point
      if (sessionStorage.getItem('__prove_seeded')) return;      // once: the page's own writes after that are the reading
      sessionStorage.setItem('__prove_seeded', '1');
      if (cls === 'H') wipe.forEach((k) => localStorage.removeItem(k));
      else localStorage.setItem('wh_hive_name', stale);
    } catch (e) { void e; }
  }, [row.cls, WIPE, STALE, !!row.baseline]);
  const p = await ctx.newPage();
  await p.setViewportSize({ width: w, height: h });
  let loads = 0;
  p.on('request', (q) => { if (q.isNavigationRequest() && q.frame() === p.mainFrame()) loads++; });
  // an uncaught error that touches the hive or its seat is this fix breaking the page (a seat awaited before it was
  // declared threw a ReferenceError and the G reading still read "no stale name" - nothing had rendered)
  const errors = [];
  p.on('pageerror', (e) => { const m = String(e && e.message || e); if (/_hiveSeated|whStartupHive|HIVE_(ID|NAME|ROLE)/.test(m)) errors.push(m.slice(0, 140)); });
  const pq = ROW_QUERY[row.page] || PAGE_QUERY[row.page];
  const q = pq ? pq + '&' : '?';
  await p.goto(`${SEEDER}/workhive/${row.page}${q}t=${Date.now()}`, { waitUntil: 'load', timeout: 60000 }).catch(() => {});
  await p.waitForTimeout(9000);            // the after-load recovery seats + reloads inside this window when it is the path
  const st = await p.evaluate(([stale, real]) => ({
    file: location.pathname.split('/').pop(),
    hive: localStorage.getItem('wh_active_hive_id'),
    name: localStorage.getItem('wh_hive_name'),
    recovered: sessionStorage.getItem('wh_hive_recovered'),
    staleShown: (document.body ? document.body.innerText : '').includes(stale),
    realShown: (document.body ? document.body.innerText : '').includes(real),
    refused: ((document.body ? document.body.innerText : '').match(/Supervisor access only|Supervisors only|Platform Admins Only|for platform admins only|Founder access only/i) || [''])[0],
    chars: document.body ? document.body.innerText.length : 0,
  }), [STALE, REAL]).catch(() => null);
  await ctx.close();
  const problems = [];
  if (errors.length) problems.push(`the page threw: ${errors[0]}`);
  if (!st) problems.push('the page never answered');
  else if (row.cls === 'H') {
    if (loads > 1 || st.recovered) problems.push(`the hive came back by a RELOAD after a solo render (${loads} document loads, wh_hive_recovered=${st.recovered}) - not in the page's start-up`);
    if (st.hive !== HIVE) problems.push(`the device ended with hive ${st.hive}, not his`);
    if (row.admitted && st.refused) problems.push(`the person this page ADMITS was refused ("${st.refused}") - the wiped role was read before the seat brought it back`);
  } else {
    if (st.staleShown) problems.push(`the stale name "${STALE}" is still on screen - the page never asked what the hive is called`);
    if (st.name !== REAL) problems.push(`the stored name is "${st.name}", not the hive's real "${REAL}"`);
    if (!BEFORE && !USE_TIME.has(row.page) && !st.realShown) problems.push(`the hive's real name "${REAL}" is not on screen - a page that never rendered would also show no stale name`);
  }
  return { ...row, vp: w, who, loads, ...(st || {}), ok: problems.length === 0, problems };
}

const results = [];
// each H row on a refusing page is read a second time, as the person it admits (outside --before: the reproduction is
// of the rows themselves)
const READINGS = BEFORE ? ROSTER : ROSTER.flatMap((r) => (r.cls === 'H' && GATED.has(r.page)) ? [r, { ...r, admitted: true }] : [r]);
// THE COMPARISON POINT FOR AN H READING (outside --before): the same person at the same width on a device that never
// lost its hive. Seated in start-up, a wiped device must render essentially that page. "Not refused" and "more than
// the refused person" both passed a variant that hid a supervisor's whole console behind the head's pre-paint class
// (1,020 characters against the page's 2,237, and a worker's wall is 482) - only the page itself is the right bar.
const FLOOR = 0.85;
for (const row of READINGS) {
  for (const vp of VPS) {
    let base = null;
    if (!BEFORE && row.cls === 'H') base = await read({ ...row, baseline: true }, vp);
    const r = await read(row, vp);
    if (base) {
      r.baseline_chars = base.chars;
      if (base.chars && r.chars < FLOOR * base.chars) {
        r.problems.push(`after the wipe the page renders ${r.chars} characters against ${base.chars} on a device that never lost its hive - the seat came back, the page did not`);
        r.ok = false;
      }
    }
    results.push(r);
    console.log(`${r.ok ? "ok  " : "FAIL"} ${r.id.padEnd(7)} ${r.cls}${r.admitted ? "+" : " "}${r.page.padEnd(32)} ${String(vp[0]).padEnd(5)} loads=${r.loads} rec=${r.recovered} stale=${r.staleShown} ${r.problems.join(' ; ').slice(0, 150)}`);
  }
}
await BROWSER.close();
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify({ _doc: 'prove_hive_startup.mjs - BRH-H/G readings, one per (row, viewport)', generated: new Date().toISOString(),
  before: BEFORE, real_name: REAL, results }, null, 1));
const bad = results.filter((r) => !r.ok);
console.log(`\n${results.length} reading(s), ${bad.length} failing; written to ${OUT}`);
if (BEFORE) {
  const held = results.filter((r) => r.ok);
  console.log(held.length ? `NOT REPRODUCED on ${held.length}: ${held.map((r) => r.id + '@' + r.vp).join(', ')}`
    : `REPRODUCED - all ${results.length} readings show the defect`);
  process.exit(held.length ? 1 : 0);
}
if (bad.length) { console.log(`FAIL hive-startup - ${bad.length} reading(s)`); process.exit(1); }
console.log('PASS hive-startup - every page that scopes by the stored hive seats a wiped one in its own start-up (one load, no '
  + 'recovery reload), and every page that shows the stored name corrects a stale one from the server');
