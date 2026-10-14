// prove_error_capture_everywhere.mjs - SL sub-layer L1 (2026-10-14): every page captures what it throws, with the page,
// the person and the engine, in WebKit AND Chromium (gate `error-capture-everywhere`).
//
// WHY. client_errors is the trail that told us why Ian's logbook died on his iPhone for a month - but it only ever
// recorded signed-in members on pages that load utils.js. The 119 public pages (learn guides, calculators, about /
// feedback / privacy / terms) load no capture at all, and the table refused anonymous inserts, so an anonymous visitor's
// error went nowhere. The fix: wh-error-capture.js (the same net without utils.js), bootstrapped by wh-i18n-lite.js and
// wh-feedback-fab.js, and migration 20261014000002 (an anonymous row may carry only the two uncaught contexts and no
// identity). This walks every page of the L1 roster, as its cast, throws an uncaught error AND an unhandled rejection
// into it after start-up, and reads what the page sent to client_errors:
//   - at least one insert per thrown kind, context `uncaught-error` / `unhandled-rejection`, carrying the probe message,
//     the page's own pathname and a user agent naming the engine;
//   - on a signed-in page with the utils.js backbone, the person too (worker_name and hive_id);
//   - on an anonymous page, NO identity (the policy refuses one).
// Inserts are intercepted and answered 201, so nothing reaches the table - except one REAL write per engine on a public
// page, which must land in the local table through the anonymous policy and is deleted after it is read.
// TEETH: the same public page served the pre-change wh-i18n-lite.js and wh-feedback-fab.js (WH_PREFIX_BASE, default
// b74b63a5, the last commit before the net) must send NOTHING - otherwise this proof cannot tell the new net from no net and fails itself.
//
//   node tools/prove_error_capture_everywhere.mjs [--engine chromium|webkit] [--class public|production|founder]
//        [--pages a.html,b/index.html] [--limit N] [--json .tmp/sl_walk2_results.json]
import { chromium, webkit } from 'playwright';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execFileSync, execSync } from 'node:child_process';
import { dirname } from 'node:path';
import { SEEDER, stubModelCalls } from './prover_harness.mjs';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const ENGINES = arg('--engine') ? [arg('--engine')] : ['chromium', 'webkit'];
const CLASS = arg('--class');
const LIMIT = Number(arg('--limit', 0));
const OUT = arg('--json', '.tmp/sl_walk2_results.json');
const BASE = process.env.WH_PREFIX_BASE || 'b74b63a5';   // the last commit before the net and its loaders
const PROBE = `sl-l1-probe-${Date.now()}`;

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
let roster = reg.trajectories.filter((t) => t.sl && t.sl.sublayer === 'L1' && t.status !== 'descoped')
  .map((t) => ({ id: t.id, page: t.sl.page, cls: t.sl.page_class, persona: t.persona }));
if (CLASS) roster = roster.filter((r) => r.cls === CLASS);
if (arg('--pages')) { const only = new Set(arg('--pages').split(',')); roster = roster.filter((r) => only.has(r.page)); }
if (LIMIT) roster = roster.slice(0, LIMIT);
const SUP = /supervisor|oversight|owner|engineer|manager/i;
const account = (persona) => (persona === 'anon' ? null
  : SUP.test(persona) ? { user: 'leandromarquez', name: 'Leandro Marquez' } : { user: 'bryangarcia', name: 'Bryan Garcia' });
const urlOf = (page) => `${SEEDER}/workhive/${page}`;
const psql = (sql) => execSync(`docker exec -i supabase_db_workhive psql -U postgres -d postgres -tA -c "${sql}"`, { encoding: 'utf8' }).trim();

async function context(engine, opts = {}) {
  const browser = await (engine === 'webkit' ? webkit : chromium).launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  await stubModelCalls(ctx);   // local stubs first: a page's load-time model call never reaches a provider
  const seen = [];
  await ctx.route('**/rest/v1/client_errors*', async (route) => {
    const req = route.request();
    if (req.method() !== 'POST') return route.continue();
    try { for (const r of [].concat(JSON.parse(req.postData() || '{}'))) seen.push(r); } catch (e) { void e; }
    if (opts.realWrite) return route.continue();               // the one real write per engine
    return route.fulfill({ status: 201, contentType: 'application/json', body: '' });
  });
  if (opts.prefix) {   // the pre-change shared scripts, from git
    for (const f of ['wh-i18n-lite.js', 'wh-feedback-fab.js']) {
      const body = execFileSync('git', ['show', `${opts.prefix}:${f}`], { encoding: 'utf8', maxBuffer: 16 << 20 })
        .replaceAll('https://hzyvnjtisfgbksicrouu.supabase.co', 'http://127.0.0.1:54321');
      await ctx.route(new RegExp(`/${f.replace('.', '\\.')}(\\?.*)?$`), (r) => r.fulfill({ status: 200, contentType: 'application/javascript', body }));
    }
  }
  return { browser, ctx, seen };
}

async function signIn(ctx, a) {
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/index.html?signin=1`, { waitUntil: 'load', timeout: 45000 });
  await p.fill('#si-username', a.user); await p.fill('#si-password', 'test1234'); await p.click('#si-btn');
  const ok = await p.waitForFunction(() => !!localStorage.getItem('wh_active_hive_id'), null, { timeout: 25000 }).then(() => true).catch(() => false);
  await p.close();
  return ok;
}

async function probe(ctx, seen, row, engine) {
  const before = seen.length;
  const p = await ctx.newPage();
  let loadError = null;
  await p.goto(urlOf(row.page), { waitUntil: 'load', timeout: 60000 }).catch((e) => { loadError = String(e.message).slice(0, 120); });
  await p.waitForTimeout(2500);
  const landed = await p.evaluate(() => location.pathname).catch(() => '?');
  await p.evaluate((msg) => {
    setTimeout(() => { throw new Error(msg); }, 0);
    setTimeout(() => { Promise.reject(new Error(msg + '-rejection')); }, 0);
  }, PROBE).catch(() => {});
  // ★POLL, DO NOT SLEEP A FIXED WINDOW (2026-10-14): a fixed 2.5 s read one learn page's rejection as uncaptured while a
  // second prover shared the CPU; alone, both kinds arrived. A capture is asynchronous (the net may still be loading,
  // or the backbone is handing the first error off), so wait for both, up to 8 s, and only then judge.
  const mineNow = () => seen.slice(before).filter((r) => String(r.message || '').startsWith(PROBE));
  for (let i = 0; i < 32; i++) {
    const m = mineNow();
    if (m.some((r) => r.context === 'uncaught-error') && m.some((r) => r.context === 'unhandled-rejection')) break;
    await p.waitForTimeout(250);
  }
  await p.close();
  const mine = mineNow();
  const problems = [];
  if (loadError) problems.push(`load: ${loadError}`);
  const want = `/workhive/${row.page}`.replace(/index\.html$/, '');
  if (!String(landed).startsWith(want.replace(/\/$/, '')) && landed !== `/workhive/${row.page}`) problems.push(`landed on ${landed}`);
  const thrown = mine.find((r) => r.context === 'uncaught-error' && r.message === PROBE);
  const rejected = mine.find((r) => r.context === 'unhandled-rejection' && r.message === `${PROBE}-rejection`);
  if (!thrown) problems.push('the thrown error was not captured');
  if (!rejected) problems.push('the unhandled rejection was not captured');
  for (const r of [thrown, rejected].filter(Boolean)) {
    if (!String(r.page || '').includes(row.page.replace(/index\.html$/, ''))) problems.push(`captured page ${r.page} is not ${row.page}`);
    const ua = String(r.user_agent || '');
    if (!ua || (engine === 'webkit' && !/AppleWebKit/.test(ua)) || (engine === 'chromium' && !/Chrome/.test(ua))) problems.push(`user agent does not name the engine: ${ua.slice(0, 60)}`);
    if (row.persona !== 'anon' && 'worker_name' in r && !r.worker_name) problems.push('a signed-in page sent no person');
    if (row.persona === 'anon' && (r.worker_name || r.hive_id)) problems.push('an anonymous page sent an identity');
  }
  return { ...row, engine, landed, captured: mine.length, person: thrown ? (thrown.worker_name || null) : null, problems, ok: !problems.length };
}

const results = [];
for (const engine of ENGINES) {
  const groups = new Map();
  for (const r of roster) { const a = account(r.persona); const k = a ? a.user : 'anon'; (groups.get(k) || groups.set(k, { a, rows: [] }).get(k)).rows.push(r); }
  for (const { a, rows } of groups.values()) {
    const { browser, ctx, seen } = await context(engine);
    const ok = a ? await signIn(ctx, a) : true;
    for (const row of rows) {
      const r = ok ? await probe(ctx, seen, row, engine) : { ...row, engine, problems: [`sign-in as ${a.user} failed`], ok: false };
      results.push(r);
      if (!r.ok) console.log(`  FAIL ${engine.padEnd(8)} ${row.page.padEnd(48)} ${r.problems.join(' | ').slice(0, 160)}`);
    }
    await browser.close();
    const ids = new Set(rows.map((x) => x.id));
    console.log(`  ${engine} ${a ? a.user : 'anon'}: ${rows.length} page(s), ${results.filter((x) => x.engine === engine && ids.has(x.id) && x.ok).length} clean`);
  }
}

// one REAL anonymous write per engine, through the policy, read back and removed
const real = [];
const pub = roster.find((r) => r.cls === 'public') || { page: 'learn/index.html', persona: 'anon' };
for (const engine of ENGINES) {
  const { browser, ctx } = await context(engine, { realWrite: true });
  const r = await probe(ctx, [], { ...pub, id: 'real-write' }, engine).catch((e) => ({ problems: [String(e.message)] }));
  await browser.close();
  const got = psql(`select count(*) from client_errors where message like '${PROBE}%' and hive_id is null and worker_name is null and auth_uid is null and user_agent ilike '%${engine === 'webkit' ? 'AppleWebKit' : 'Chrome'}%'`);
  real.push({ engine, page: pub.page, rows_in_table: Number(got) });
}
psql(`delete from client_errors where message like '${PROBE}%'`);

// teeth: the same public page, the pre-change shared scripts
let teeth = null;
{
  const { browser, ctx, seen } = await context('chromium', { prefix: BASE });
  teeth = await probe(ctx, seen, { ...pub, id: 'teeth' }, 'chromium');
  await browser.close();
  teeth.bit = teeth.captured === 0;
}

mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify({ _doc: 'prove_error_capture_everywhere.mjs - SL L1 readings, one per (page, engine)', generated: new Date().toISOString(),
  probe: PROBE, base: BASE, results, real, teeth }, null, 1));
const bad = results.filter((r) => !r.ok);
console.log(`\n  real anonymous writes through the policy: ${real.map((x) => `${x.engine} ${x.rows_in_table} row(s)`).join(', ')} (removed after reading)`);
console.log(`  teeth - ${pub.page} with the pre-change scripts (${BASE}): ${teeth.bit ? 'captured NOTHING, as it must' : `captured ${teeth.captured}`}`);
console.log(`\n${results.length} reading(s), ${bad.length} failing; written to ${OUT}`);
const realOk = real.every((x) => x.rows_in_table >= 2);
if (!teeth.bit) { console.log('FAIL error-capture-everywhere - NO TEETH: the pre-change scripts captured too'); process.exit(1); }
if (!realOk) { console.log('FAIL error-capture-everywhere - an anonymous error did not land in the table through the policy'); process.exit(1); }
if (bad.length) { console.log(`FAIL error-capture-everywhere - ${bad.length} reading(s)`); process.exit(1); }
console.log('PASS error-capture-everywhere - every L1 page captures a thrown error and a rejection, with its page, its person where it has '
  + 'one and the engine, in WebKit and Chromium; an anonymous error lands through the policy; the pre-change scripts captured nothing');
