// prove_skew_heal.mjs - BRH-D (2026-10-14): a page that relies on shared functions HEALS an older utils.js instead of
// silently running without them.
//
// WHY. Ian's missing hive assets: the new logbook ran on an hour-old utils.js that lacked the function it needed, and its
// `typeof whX === 'function'` guard turned the skew into silence. 31 production pages guard 51 utils.js functions that
// way. tools/render_skew_heal.py writes one block per page, right after its utils.js tag, that names them; this prover
// shows the block WORKS in a browser, per page, at 390 AND 1280, signed in through the product's own client:
//
//   clean   the real utils.js: the page does NOT heal - no fetch of utils.js, one navigation, every named function there
//           (a false heal would cost every visitor a reload)
//   skew    "yesterday's utils.js": the current file with the page's own functions set to undefined at its end (renaming
//           the definitions instead can make utils.js throw before getDb exists, which is a different failure) - served
//           to every <script> load until the page fetches utils.js past the cache, as an HTTP or service-worker copy
//           would be. The page must fetch it past the cache, reload once, and end with every function there.
//   stuck   (achievements, logbook at 390) no fresh copy exists at all - the refetch answers the old file too. The page
//           must refetch ONCE, reload ONCE and then stay put with the guard set: the heal must never loop. (The block
//           clears its guard after a clean reload, so a guard read AFTER a successful heal is empty by design; the
//           loop-safety is proven here, where the heal cannot succeed.)
//   TEETH   the same skew walk against pages from WH_PREFIX_BASE (default 7db71ff4, before the blocks): they must come
//           back still lacking the functions and with no refetch - the defect Ian met - or the prover FAILS itself.
//
//   node tools/prove_skew_heal.mjs [--page a.html,b.html] [--viewport 390] [--json .tmp/skew_heal_results.json]
//        [--before]   walk EVERY page as it is on disk with no heal expected: the reproduction, demonstrated failing
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname } from 'node:path';
import { SEEDER, HIVE, signIn, stubModelCalls, PAGE_QUERY } from './prover_harness.mjs';
import { ALL_ROWS_DRAWN } from './lib/long_list_text.mjs';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const OUT = arg('--json', '.tmp/skew_heal_results.json');
const BASE = process.env.WH_PREFIX_BASE || '7db71ff4';
const BEFORE = process.argv.includes('--before');
const TEETH_PAGES = ['asset-hub.html', 'marketplace.html'];
const VPS = (arg('--viewport') ? [Number(arg('--viewport'))] : [390, 1280]).map((w) => [w, w === 390 ? 844 : 800]);
const PY = process.platform === 'win32' ? 'python' : 'python3';

const NEEDS = JSON.parse(execFileSync(PY, ['tools/render_skew_heal.py', '--needs-json'], { encoding: 'utf8', maxBuffer: 16 << 20 }));
const PAGES = arg('--page') ? arg('--page').split(',') : Object.keys(NEEDS).sort();
const ACCT = { name: 'Leandro Marquez', first: 'Leandro', role: 'supervisor', email: 'leandromarquez@auth.workhiveph.com', password: 'test1234' };

const BROWSER = await chromium.launch();
let STATE = null;
{
  const ctx = await BROWSER.newContext({ serviceWorkers: 'block' });
  await ctx.addInitScript(ALL_ROWS_DRAWN);
  if (await signIn(ctx, { ...ACCT, hive: HIVE })) {
    const p = await ctx.newPage();
    await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
    STATE = await ctx.storageState();
  }
  await ctx.close();
}
if (!STATE) { console.log('FAIL skew-heal-live - SIGN-IN FAILED, nothing was read'); process.exit(1); }

async function walk(page, [w, h], mode, base) {
  const need = NEEDS[page] || [];
  const ctx = await BROWSER.newContext({ serviceWorkers: 'block', storageState: STATE });
  await ctx.addInitScript(ALL_ROWS_DRAWN);
  await stubModelCalls(ctx);
  await ctx.route('**/functions/v1/**', (r) => r.request().method() === 'OPTIONS' ? r.fallback()
    : r.fallback({ headers: { ...r.request().headers(), 'x-wh-walk-no-model': '1' } }));
  // each utils.js request is kept WITH the document that made it: an old page that bounces the person elsewhere (the
  // pre-heal asset-hub sent them to the landing page, whose own heal then refetched) must not be credited with a refetch
  // it never made - the verdict reads only the page under test's own requests
  const seq = [];
  const fileOf = (u) => { try { return new URL(u).pathname.split('/').pop(); } catch (e) { return ''; } };
  let refreshed = false;
  await ctx.route('**/utils.js*', async (route) => {
    const kind = route.request().resourceType();
    let doc = ''; try { doc = fileOf(route.request().frame().url()); } catch (e) { void e; }
    // STUCK: no fresh copy can be had at all (the refetch answers the old file too) - the heal must give up after one
    // reload, never loop; that is what its once-per-tab guard is for
    if (kind === 'fetch') { refreshed = true; seq.push({ k: 'fetch', doc }); if (mode !== 'stuck') return route.fallback(); }
    else if (mode === 'clean' || (mode === 'skew' && refreshed)) { seq.push({ k: 'script', doc }); return route.fallback(); }
    else seq.push({ k: 'script:old', doc });
    const resp = await route.fetch();
    const body = (await resp.text()) + '\n;' + need.map((n) => `window.${n} = undefined;`).join('') + '\n';
    return route.fulfill({ response: resp, body, headers: { ...resp.headers(), 'cache-control': 'no-store' } });
  });
  if (base) {
    const old = execFileSync('git', ['show', `${base}:${page}`], { encoding: 'utf8', maxBuffer: 64 << 20 });
    await ctx.route(new RegExp(`/workhive/${page.replace(/\./g, '\\.')}(\\?.*)?$`), (r) =>
      r.request().resourceType() === 'document' ? r.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: old }) : r.fallback());
  }
  const p = await ctx.newPage();
  await p.setViewportSize({ width: w, height: h });
  // document LOADS of the main frame, not framenavigated: a page's own history.pushState (assistant's chat back-stack)
  // is a same-document entry, never a reload
  let navs = 0;
  p.on('request', (q) => { if (q.isNavigationRequest() && q.frame() === p.mainFrame()) navs++; });
  // the page under test is the FIRST document this tab loads: a fresh context has no sessionStorage, so the block's
  // once-per-tab guard starts clear - and no other page (index.html carries a heal of its own) can spend the refetch
  const q = PAGE_QUERY[page] ? PAGE_QUERY[page] + '&' : '?';
  await p.goto(`${SEEDER}/workhive/${page}${q}t=${Date.now()}`, { waitUntil: 'commit', timeout: 60000 }).catch(() => {});
  // the heal stops the first document and reloads: wait until the page has settled on a document whose utils.js ran
  let st = null;
  for (let i = 0; i < 40; i++) {
    await p.waitForTimeout(500);
    st = await p.evaluate((names) => ({
      ready: document.readyState, file: location.pathname.split('/').pop(), utils: typeof window.getDb === 'function',
      missing: names.filter((n) => typeof window[n] !== 'function'),
      flag: (() => { try { return sessionStorage.getItem('wh_utils_refetched'); } catch (e) { return 'blocked'; } })(),
      chars: document.body ? document.body.innerText.length : 0,
      navType: (() => { try { const e = performance.getEntriesByType('navigation')[0]; return e ? e.type : ''; } catch (e) { return ''; } })(),
    }), need).catch(() => null);
    // a skew reading waits for the RELOAD, not the refetch: between the two, the stopped old document already reads
    // 'complete' with getDb present (analytics at 1280 was read there and looked unhealed). ★And navs >= 2 is not the
    // reload either (SL AV4 gate run, 2026-10-20: index.html at 1280 read 14 of 14 missing): a navigation REQUEST is
    // counted the moment it is sent, while the old stopped document is still the one being read. Only a document whose
    // own navigation entry says 'reload' is the healed one.
    if (st && st.ready === 'complete' && st.utils && (mode === 'clean' || (refreshed && navs >= 2 && st.navType === 'reload') || i >= 16)) break;
  }
  if (mode === 'stuck') {
    // after the one reload, watch: a heal that loops would load the document again (and again)
    await p.waitForTimeout(6000);
    st = await p.evaluate((names) => ({
      ready: document.readyState, file: location.pathname.split('/').pop(), utils: typeof window.getDb === 'function',
      missing: names.filter((n) => typeof window[n] !== 'function'),
      flag: (() => { try { return sessionStorage.getItem('wh_utils_refetched'); } catch (e) { return 'blocked'; } })(),
      chars: document.body ? document.body.innerText.length : 0,
    }), need).catch(() => st);
  }
  await ctx.close();
  const own = seq.filter((x) => x.doc === page).map((x) => x.k);
  const r = { page, vp: w, mode, base: base || null, need: need.length, seq: own,
    elsewhere: seq.filter((x) => x.doc !== page).map((x) => `${x.k}@${x.doc}`), navs, ...(st || {}) };
  const problems = [];
  if (!st) problems.push('the page never answered');
  else if (st.file !== page) {
    problems.push(`ended on ${st.file}, not ${page}`);
    if (mode === 'skew' && !own.includes('fetch')) problems.push(`the page never fetched utils.js past the cache: it ran on the old copy (${own.join(' > ')}) and then left`);
  } else if (mode === 'stuck') {
    const fetches = own.filter((k) => k === 'fetch').length;
    if (!st.missing.length) problems.push('VACUOUS stuck walk: the page ended with every function, so no old copy was held');
    if (fetches !== 1) problems.push(`with no fresh copy to be had the page refetched ${fetches} time(s) - one refetch, then give up`);
    if (navs > 2) problems.push(`with no fresh copy to be had the page loaded ${navs} times - the heal LOOPS`);
    if (st.flag !== '1') problems.push(`the once-per-tab guard is ${st.flag} after a heal that could not succeed - nothing stops the next load from reloading`);
  } else if (mode === 'clean') {
    if (own.includes('fetch')) problems.push('a clean load HEALED (fetched utils.js past the cache) - a false heal reloads every visitor');
    if (navs > 1) problems.push(`a clean load loaded the document ${navs} times`);
    if (st.missing.length) problems.push(`with the real utils.js the page still lacks ${st.missing.join(', ')}`);
  } else {
    if (!own.includes('fetch')) problems.push(`the page never fetched utils.js past the cache: it ran on the old copy (${own.join(' > ')})`);
    if (st.missing.length) problems.push(`it ended lacking ${st.missing.length} of ${need.length}: ${st.missing.slice(0, 4).join(', ')}${st.missing.length > 4 ? ' ...' : ''} - every guarded call silently does nothing`);
    if (navs < 2 && own.includes('fetch')) problems.push('it refetched but never reloaded');
  }
  r.ok = problems.length === 0;
  r.problems = problems;
  return r;
}

const results = [];
for (const page of PAGES) {
  for (const vp of VPS) {
    for (const mode of (BEFORE ? ['skew'] : ['clean', 'skew'])) {
      const r = await walk(page, vp, mode, null);
      results.push(r);
      console.log(`${r.ok ? 'ok  ' : 'FAIL'} ${page.padEnd(32)} ${String(vp[0]).padEnd(5)} ${mode.padEnd(6)} needs=${String(r.need).padEnd(3)} ${(r.seq || []).join('>').padEnd(26)} navs=${r.navs} ${r.problems.join(' ; ').slice(0, 170)}`);
    }
  }
}

// the loop-safety reading: two pages (one with its utils.js in <head>, one late in <body>) where no fresh copy exists
const LOOP_PAGES = ['achievements.html', 'logbook.html'];
const loops = [];
if (!BEFORE) {
  for (const page of LOOP_PAGES.filter((p) => NEEDS[p] && (!arg('--page') || PAGES.includes(p)))) {
    const r = await walk(page, VPS[0], 'stuck', null);
    loops.push(r);
    results.push(r);
    console.log(`${r.ok ? 'ok  ' : 'FAIL'} ${page.padEnd(32)} ${String(VPS[0][0]).padEnd(5)} stuck  needs=${String(r.need).padEnd(3)} ${(r.seq || []).join('>').padEnd(26)} navs=${r.navs} flag=${r.flag} ${r.problems.join(' ; ').slice(0, 150)}`);
  }
}

let teeth = null;
if (!BEFORE) {
  const t = [];
  for (const page of TEETH_PAGES.filter((p) => NEEDS[p])) t.push(await walk(page, VPS[0], 'skew', BASE));
  const bit = t.length > 0 && t.every((r) => !r.ok && !(r.seq || []).includes('fetch'));
  teeth = { base: BASE, bit, readings: t.map((r) => ({ page: r.page, seq: r.seq, elsewhere: r.elsewhere, file: r.file, missing: r.missing, problems: r.problems })) };
  console.log(`\n  teeth - ${t.map((r) => r.page).join(', ')} at ${BASE}: ${bit ? 'run on the old utils.js as they must' : 'DID NOT FAIL'}`);
}

await BROWSER.close();
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify({ _doc: 'prove_skew_heal.mjs - BRH-D readings, one per (page, viewport, mode)', generated: new Date().toISOString(),
  before: BEFORE, base: BASE, results, teeth }, null, 1));
const bad = results.filter((r) => !r.ok);
console.log(`\n${results.length} reading(s), ${bad.length} failing; written to ${OUT}`);
if (BEFORE) {
  // the reproduction: every page must FAIL its skew walk before the heal exists
  const healed = results.filter((r) => r.ok);
  console.log(healed.length ? `NOT REPRODUCED on ${healed.length} reading(s): ${healed.map((r) => r.page + '@' + r.vp).join(', ')}`
    : `REPRODUCED - all ${results.length} skew readings ran on the old utils.js without a refetch`);
  process.exit(healed.length ? 1 : 0);
}
if (!teeth.bit) { console.log('FAIL skew-heal-live - NO TEETH: the pre-heal pages did not run on the old utils.js'); process.exit(1); }
if (bad.length) { console.log(`FAIL skew-heal-live - ${bad.length} reading(s)`); process.exit(1); }
console.log('PASS skew-heal-live - every page that relies on shared functions, at 390 and 1280, leaves a current utils.js '
  + 'alone and heals an old one (refetch past the cache, one reload, every function there); the pre-heal pages do not');
