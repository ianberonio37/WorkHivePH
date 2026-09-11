// prove_reference_fourth_state — P-I "the fourth state" on the reference surfaces (2026-09-05).
//
// A reference page reads a local JSON/JS file. Empty (0 rows), loading, and loaded are three states a
// gate can see; the FOURTH is the read that FAILED (network, 404, 5xx). A page that keeps saying
// "Loading..." or paints nothing after a failed read is a stuck skeleton no static gate catches.
// For each page: abort its data request(s), wait, then require that the status/content region says
// something a person can act on (failed / unavailable / could not / retry / offline / try again) and
// is NOT still "Loading".
//   node tools/prove_reference_fourth_state.mjs            # all pages; exit 1 on any stuck page
//   node tools/prove_reference_fourth_state.mjs --page validator-catalog.html
import { chromium } from 'playwright';

import { SEEDER, VIS_JS, SETTLE_MS } from './prover_harness.mjs';   // shared preamble (2026-09-05): checkVisibility, the settle envelope
const PAGES = [
  { file: 'validator-catalog.html', block: /platform_health\.json|VALIDATOR_REGISTRY\.json/, status: '#meta, [role="status"]', content: '#tbl tbody' },
  { file: 'design-system.html',     block: /design_component_registry\.json|component_purity_baseline\.json|storage_key_registry\.json|ufai-rubric-spec\.json|family_rubric_scoreboard\.json/, status: '[role="status"], .wh-source-chip, #ds-prov, #ds-axes', content: '#ds-root' },
  { file: 'symbol-gallery.html',    block: /drawing-symbols\.js/, status: '#sym-count, [role="status"]', content: '#gallery' },
  { file: 'llm-observability.html', block: /rest\/v1\/ai_cost_log|rest\/v1\/ai_cache/, status: '#meta, [role="status"]', content: '#by-task tbody, .grid' },
  { file: 'architecture.html',      block: /platform_catalog\.json|substrate_manifest\.json|\.json$/, status: '[role="status"], .wh-source-chip', content: 'main' },
  { file: 'offline-fallback.html',  block: /x^/, status: '#net-hint, [role="status"]', content: 'main, body' },
  { file: 'agentic-rag-observability.html', block: /rest\/v1\/agentic_rag_traces/, status: '#freshness, [role="status"], .honest-empty', content: 'main, body' },   // P450 degradation is legible (2026-09-05)
];
const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
// --shared: P-L 'systemic ripple' - abort the SHARED deps every page leans on (utils.js, tokens.css, the feedback
// and wayfinding scripts) and require the page to still paint its OWN content: a static reference page must not
// go blank because a shared script did not arrive (progressive enhancement, measured 2026-09-05).
const SHARED = process.argv.includes('--shared');
const SHARED_RE = /\/(utils|wh-feedback-fab|wayfinding|offline-banner|maturity-gate)\.js|\/tokens\.css/;
const FAIL_WORDS = /fail|unavailable|could not|couldn.t|retry|try again|offline|not load|error|unreachable/i;
const STUCK_WORDS = /loading|counting|fetching|\.\.\.$|…$/i;

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
let bad = 0, n = 0;
for (const pg of PAGES) {
  if (ONLY && pg.file !== ONLY) continue;
  n++;
  const p = await ctx.newPage();
  const errs = []; p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 140)); }); p.on('pageerror', (e) => errs.push('PAGEERR ' + String(e.message).slice(0, 140)));
  let blocked = 0;
  const blockRe = SHARED ? SHARED_RE : pg.block;
  await p.route('**/*', (route) => { const u = route.request().url(); if (blockRe.test(u) && !/\.html($|\?)/.test(u)) { blocked++; return route.abort('failed'); } return route.continue(); });
  await p.goto(`${SEEDER}/workhive/${pg.file}`, { waitUntil: 'load' }).catch(() => {});
  // 12s: utils.js's fetch wrapper retries a failed read four times with backoff (1.6s -> 8.7s, measured on
  // llm-observability 2026-09-05) before the page can say so; the honest envelope is the platform's, not 6.5s.
  await p.waitForTimeout(SETTLE_MS);   // the retry envelope + the last settle pass
  await p.evaluate((v) => { window.__whVis = (0, eval)(v); }, VIS_JS).catch(() => {});   // a fixed-position notice has no offsetParent
  const r = await p.evaluate(({ status, content }) => {
    const vis = window.__whVis || ((e) => e && e.offsetParent !== null);
    const st = [...document.querySelectorAll(status)].filter(vis).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
    const c = document.querySelector(content);
    const ctext = c ? (c.innerText || '').replace(/\s+/g, ' ').trim() : '';
    return { status: st.join(' | ').slice(0, 200), contentLen: ctext.length, contentHead: ctext.slice(0, 120) };
  }, { status: pg.status, content: pg.content }).catch(() => ({ status: '', contentLen: 0, contentHead: '' }));
  // Only the STATUS region or a visible alert/error element counts - a body-wide word match let a page whose
  // status still read 'Loading...' pass on a static 'FAIL only' option (first run, 2026-09-05).
  const bodyLen = await p.evaluate(() => (document.body && document.body.innerText || '').replace(/\s+/g, ' ').trim().length).catch(() => 0);
  const alertText = await p.evaluate(() => [...document.querySelectorAll('[role="alert"], .honest-empty, .wh-list-error')].filter(window.__whVis || ((e) => e.offsetParent !== null)).map((e) => (e.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean).join(' | ')).catch(() => '');
  const says = FAIL_WORDS.test(r.status) || FAIL_WORDS.test(alertText);
  if (process.env.WH_FOURTH_DEBUG) console.log(`    [debug] status="${r.status.slice(0, 160)}" alerts="${alertText.slice(0, 160)}" head="${r.contentHead}" errors=${JSON.stringify(errs.slice(0, 4))}`);
  const stuck = STUCK_WORDS.test(r.status) && !says;
  const verdict = says ? 'SAYS-FAILED' : (stuck ? 'STUCK-LOADING' : (r.contentLen > 40 ? 'SILENT (content painted from elsewhere)' : 'SILENT-EMPTY'));
  if (blocked === 0) { console.log(`  n/a ${pg.file.padEnd(24)} no data request matched the block pattern - nothing to fail (page is static)`); await p.close(); n--; continue; }
  if (SHARED) {
    // ripple verdict: the page's own content root still paints (>200 chars) and the body is not blank
    // the CONTENT ROOT must paint (body chrome alone is not the page) - or the page must say the shared script failed
    const own = r.contentLen > 200 || FAIL_WORDS.test(r.status) || FAIL_WORDS.test(alertText);
    if (!own) bad++;
    console.log(`  ${own ? 'ok ' : 'BAD'} ${pg.file.padEnd(24)} shared deps aborted (${blocked}) -> ${own ? 'own content still paints' : 'BLANK / stripped'}: content=${r.contentLen}ch body=${bodyLen}ch`);
    await p.close(); continue;
  }
  const ok = says;
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${pg.file.padEnd(24)} blocked=${blocked} verdict=${verdict} status="${r.status.slice(0, 90)}" content=${r.contentLen}ch`);
  await p.close();
}
await b.close();
console.log(SHARED ? `${bad ? 'FAIL' : 'PASS'} reference-shared-ripple - ${n - bad}/${n} reference pages still paint their own content with the shared deps aborted` : `${bad ? 'FAIL' : 'PASS'} reference-fourth-state - ${n - bad}/${n} reference pages say so when their data read fails`);
process.exit(bad ? 1 : 0);
