// prove_page_survives_optional_failures.mjs - SL sub-layers A3, AV1 and H1 (2026-10-14): a page's start-up completes in
// WebKit AND Chromium under the CSP production ships, and still completes when every OPTIONAL subsystem fails - and in
// neither case does the page throw anything into client_errors.
//
// WHY. The real cause of Ian's missing logbook assets (2026-10-14): production's CSP named only https: for Supabase,
// WebKit THROWS SecurityError from `new WebSocket` under such a CSP (Chromium fails it quietly), and the logbook's
// async start-up died on the live badge before it loaded the assets. Production's client_errors had recorded it for a
// month on NINE pages (production_error_groups.json). `prove_realtime_blocked_socket.mjs` proved the fix on ONE page in
// Chromium with the socket forced to throw; this generalises it to the pages production named, to every optional
// subsystem, and to the real WebKit engine, with production's OWN signal as the verdict: an insert into client_errors
// with context `uncaught-error` or `unhandled-rejection` is exactly what the iPhone wrote on every visit.
//
// Per (page, engine, condition), signed in as the page's cast through the product's own sign-in form:
//   condition as-served     the document carries the SHIPPED vercel.json CSP and Permissions-Policy, with only the
//                           production Supabase origins mapped to the local stack (so WebKit enforces production's
//                           policy against the page's real connections - sub-layer H1)
//   condition optional-fail as-served, plus every optional subsystem failing the way a real device fails it: the
//                           WebSocket constructor throws SecurityError, indexedDB.open throws (private mode),
//                           speechSynthesis is absent, geolocation errors, Notification throws, share/clipboard reject,
//                           and the page-view / analytics writes are refused at the network (sub-layer A3)
// Verdict: no client_errors insert with an UNCAUGHT context (they are intercepted and answered 201, so nothing reaches
// the local table), no pageerror, no CSP violation, the page rendered (chars >= floor) and no busy indicator lingers.
// A caught error the page logs on purpose (another context) is recorded, not failed - that is L1 working.
// TEETH: the pre-fix logbook (utils.js + logbook.html at WH_PREFIX_BASE, default 90ed9a8e) under optional-fail must
// produce an uncaught insert; if it does not, the proof cannot tell a dead start-up from a live one and FAILS itself.
//
//   node tools/prove_page_survives_optional_failures.mjs [--engine webkit|chromium] [--page logbook.html]
//        [--condition as-served|optional-fail] [--no-teeth] [--json .tmp/sl_walk1_results.json]
import { chromium, webkit } from 'playwright';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname } from 'node:path';
import { SEEDER } from './prover_harness.mjs';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const ENGINES = arg('--engine') ? [arg('--engine')] : ['chromium', 'webkit'];
const ALL = process.argv.includes('--all');   // every page of the SL roster (H1 / S3), as served only unless --condition
const CONDITIONS = arg('--condition') ? [arg('--condition')] : (ALL ? ['as-served'] : ['as-served', 'optional-fail']);
const OUT = arg('--json', '.tmp/sl_walk1_results.json');
const TEETH = !process.argv.includes('--no-teeth');
const BASE = process.env.WH_PREFIX_BASE || '90ed9a8e';
const PROD_HOST = 'hzyvnjtisfgbksicrouu.supabase.co';
const LOCAL = '127.0.0.1:54321';
const CHARS_FLOOR = 300;

// the pages production's client_errors named (production_error_groups.json), each walked as its SL cast
const groups = JSON.parse(readFileSync('production_error_groups.json', 'utf8')).groups.map((g) => g.page);
const reg0 = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const rosterPages = [...new Set(reg0.trajectories.filter((t) => t.sl && t.sl.sublayer === 'AV1' && t.status !== 'descoped').map((t) => t.sl.page))];
const PAGES = arg('--page') ? arg('--page').split(',') : (ALL ? rosterPages : groups);
const reg = reg0;
const castOf = (page) => (reg.trajectories.find((t) => t.sl && t.sl.page === page && t.sl.sublayer === 'AV1') || {}).persona || 'worker';
// the hub's two modes: a supervisor-cast persona walks as Leandro Marquez, a field-cast one as Bryan Garcia (Baguio)
const SUP = /supervisor|oversight|owner|engineer|manager/i;
const ACCOUNT = (persona) => persona === 'anon' ? { user: 'anon', name: 'an anonymous visitor' } : (SUP.test(persona)
  ? { user: 'leandromarquez', name: 'Leandro Marquez' } : { user: 'bryangarcia', name: 'Bryan Garcia' });

// the shipped policy, with only the production Supabase origins mapped to the local stack. img-src keeps `https:` (how
// production reaches its storage images) and gains the local http origin that stands in for it.
const vercel = JSON.parse(readFileSync('vercel.json', 'utf8'));
const hdr = (k) => (vercel.headers || []).flatMap((h) => h.headers || []).find((h) => h.key.toLowerCase() === k)?.value || '';
const SHIPPED_CSP = hdr('content-security-policy');
const LOCAL_CSP = SHIPPED_CSP.replaceAll(`https://${PROD_HOST}`, `http://${LOCAL}`).replaceAll(`wss://${PROD_HOST}`, `ws://${LOCAL}`)
  .replace(/img-src ([^;]*)/, (m, v) => `img-src ${v} http://${LOCAL}`);
const PERMISSIONS = hdr('permissions-policy');
if (!SHIPPED_CSP.includes(`wss://${PROD_HOST}`)) { console.log('FAIL - vercel.json CSP does not name the realtime socket'); process.exit(1); }

// the pre-fix files come from git as committed, so they get the SAME cloud->local rewrite the seeder applies to every
// page and script it serves (test-data-seeder/app.py _rewrite: URL and publishable key), read from that file rather
// than retyped - or the teeth would fail for the wrong reason (a page talking to the cloud, not a dead start-up)
const SEEDER_APP = readFileSync('test-data-seeder/app.py', 'utf8');
const KEY = (name) => (SEEDER_APP.split(/\r?\n/).find((l) => l.startsWith(`${name} = "`)) || '').split('"')[1];
const REWRITE = (t) => t.replaceAll(`https://${PROD_HOST}`, `http://${LOCAL}`).replaceAll(KEY('CLOUD_KEY'), KEY('LOCAL_KEY'));
if (!KEY('CLOUD_KEY') || !KEY('LOCAL_KEY')) { console.log('FAIL - could not read the seeder rewrite keys'); process.exit(1); }
const UNCAUGHT = new Set(['uncaught-error', 'unhandled-rejection']);
const OPTIONAL_FAIL = () => {
  const deny = (name) => () => { throw new DOMException('The operation is insecure.', 'SecurityError'); };
  window.WebSocket = function () { throw new DOMException('The operation is insecure.', 'SecurityError'); };
  try { Object.defineProperty(window, 'indexedDB', { value: { open: deny('indexedDB'), deleteDatabase: deny('indexedDB') }, configurable: true }); } catch (e) { void e; }
  try { Object.defineProperty(window, 'speechSynthesis', { value: undefined, configurable: true }); } catch (e) { void e; }
  try { navigator.geolocation.getCurrentPosition = (ok, err) => err && err({ code: 1, message: 'User denied Geolocation' }); } catch (e) { void e; }
  try { window.Notification = function () { throw new DOMException('Notifications are blocked', 'NotAllowedError'); }; window.Notification.permission = 'denied'; window.Notification.requestPermission = () => Promise.resolve('denied'); } catch (e) { void e; }
  try { navigator.share = () => Promise.reject(new DOMException('Share is not allowed', 'NotAllowedError')); } catch (e) { void e; }
  try { Object.defineProperty(navigator, 'clipboard', { value: { writeText: () => Promise.reject(new DOMException('Clipboard blocked', 'NotAllowedError')), readText: () => Promise.reject(new DOMException('Clipboard blocked', 'NotAllowedError')) }, configurable: true }); } catch (e) { void e; }
};
const LISTEN = () => {
  window.__cspv = [];
  document.addEventListener('securitypolicyviolation', (e) => window.__cspv.push(`${e.violatedDirective} ${e.blockedURI}`));
};

async function context(engine, condition, prefix) {
  // ★A HARNESS ARTIFACT, NOT A PAGE DEFECT (2026-10-14): Chromium's Local Network Access treats a document this prover
  // FULFILS (to attach production's CSP) as outside the loopback space, so every call it makes to the local stack at
  // 127.0.0.1:54321 is refused ("Permission was denied for this request to access the loopback address space") and the
  // sign-in never completes. In production the page and Supabase are both public origins, so the check cannot fire.
  const browser = await (engine === 'webkit' ? webkit : chromium).launch(engine === 'webkit' ? {} : {
    args: ['--disable-features=LocalNetworkAccessChecks,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights'] });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  const seen = { inserts: [] };
  await ctx.route('**/rest/v1/client_errors*', async (route) => {
    const req = route.request();
    if (req.method() === 'POST') {
      try { const b = JSON.parse(req.postData() || '{}'); for (const r of [].concat(b)) seen.inserts.push({ context: r.context, message: String(r.message || '').slice(0, 160), page: r.page }); } catch (e) { void e; }
      return route.fulfill({ status: 201, contentType: 'application/json', body: '[]' });
    }
    return route.continue();
  });
  // every document is served with production's policy (WebKit enforces it; that is the point)
  await ctx.route(/\/workhive\/[^?]*\.html(\?.*)?$/, async (route) => {
    const url = new URL(route.request().url());
    const file = url.pathname.replace(/^\/workhive\//, '');
    let body;
    if (prefix && file === 'logbook.html') body = REWRITE(execFileSync('git', ['show', `${prefix}:logbook.html`], { encoding: 'utf8', maxBuffer: 64 << 20 }));
    else { const r = await route.fetch(); body = await r.text(); }
    return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body,
      headers: { 'Content-Security-Policy': LOCAL_CSP, 'Permissions-Policy': PERMISSIONS, 'Cache-Control': 'no-store' } });
  });
  if (prefix) {
    const oldUtils = REWRITE(execFileSync('git', ['show', `${prefix}:utils.js`], { encoding: 'utf8', maxBuffer: 64 << 20 }));
    await ctx.route('**/utils.js*', (r) => r.fulfill({ status: 200, contentType: 'application/javascript', body: oldUtils }));
  }
  await ctx.addInitScript(LISTEN);
  if (condition === 'optional-fail') {
    await ctx.addInitScript(OPTIONAL_FAIL);
    await ctx.route(/\/rest\/v1\/(page_views|analytics_events)/, (r) => r.abort('failed'));
  }
  return { browser, ctx, seen };
}

async function signIn(ctx, account) {
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/index.html?signin=1`, { waitUntil: 'load', timeout: 45000 });
  await p.fill('#si-username', account.user);
  await p.fill('#si-password', 'test1234');
  await p.click('#si-btn');
  const ok = await p.waitForFunction(() => !!localStorage.getItem('wh_active_hive_id'), null, { timeout: 25000 }).then(() => true).catch(() => false);
  await p.close();
  return ok;
}

async function visit(ctx, seen, page) {
  const before = seen.inserts.length;
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', (e) => errors.push(String(e && e.message || e).slice(0, 160)));
  let loadError = null;
  await p.goto(`${SEEDER}/workhive/${page}`, { waitUntil: 'load', timeout: 60000 }).catch((e) => { loadError = String(e.message).slice(0, 120); });
  await p.waitForLoadState('networkidle', { timeout: 12000 }).catch(() => {});
  await p.waitForTimeout(4000);
  const st = await p.evaluate(() => {
    const vis = (e) => !!e && (typeof e.checkVisibility === 'function' ? e.checkVisibility() : e.offsetParent !== null);
    const busy = [...document.querySelectorAll('[aria-busy="true"], .wh-skeleton, .skeleton, .loading-spinner')].filter(vis).length;
    return { chars: (document.body.innerText || '').replace(/\s+/g, ' ').trim().length, busy, cspv: (window.__cspv || []).slice(0, 6),
      url: location.pathname.split('/').pop(), assets: (typeof _assets !== 'undefined' && Array.isArray(_assets)) ? _assets.length : null };
  }).catch((e) => ({ chars: 0, busy: 0, cspv: [], url: '?', evalError: String(e.message).slice(0, 120) }));
  await p.close();
  const inserts = seen.inserts.slice(before);
  const uncaught = inserts.filter((i) => UNCAUGHT.has(i.context));
  const problems = [];
  if (loadError) problems.push(`load: ${loadError}`);
  if (st.url !== page) problems.push(`landed on ${st.url}, not ${page}`);
  if (uncaught.length) problems.push(`client_errors: ${uncaught.map((i) => `${i.context}: ${i.message}`).join(' | ')}`);
  if (errors.length) problems.push(`pageerror: ${errors.join(' | ')}`);
  if (st.cspv.length) problems.push(`CSP violation: ${st.cspv.join(' | ')}`);
  if (st.chars < CHARS_FLOOR) problems.push(`rendered ${st.chars} characters`);
  if (st.busy) problems.push(`${st.busy} busy indicator(s) still showing after settle`);
  return { page, chars: st.chars, assets: st.assets, logged: inserts.filter((i) => !UNCAUGHT.has(i.context)).map((i) => `${i.context}: ${i.message}`), problems };
}

const results = [];
for (const engine of ENGINES) {
  for (const condition of CONDITIONS) {
    const byAccount = new Map();
    for (const page of PAGES) { const a = ACCOUNT(castOf(page)); (byAccount.get(a.user) || byAccount.set(a.user, { a, pages: [] }).get(a.user)).pages.push(page); }
    for (const { a, pages } of byAccount.values()) {
      const { browser, ctx, seen } = await context(engine, condition, null);
      const ok = a.user === 'anon' ? true : await signIn(ctx, a);   // a public page is read as the visitor it is for
      for (const page of pages) {
        const r = ok ? await visit(ctx, seen, page) : { page, problems: [`sign-in as ${a.user} failed - no reading taken`] };
        results.push({ engine, condition, cast: castOf(page), account: a.user, ...r, ok: !r.problems.length });
        console.log(`  ${r.problems.length ? 'FAIL' : 'ok  '} ${engine.padEnd(8)} ${condition.padEnd(13)} ${page.padEnd(20)} as ${castOf(page).padEnd(16)} ${r.chars ?? '-'} chars`
          + (r.problems.length ? `\n         ${r.problems.join('\n         ')}` : ''));
      }
      await browser.close();
    }
  }
}

let teeth = null;
if (TEETH) {
  const { browser, ctx, seen } = await context('chromium', 'optional-fail', BASE);
  const ok = await signIn(ctx, ACCOUNT(castOf('logbook.html')));
  teeth = ok ? await visit(ctx, seen, 'logbook.html') : { problems: ['teeth sign-in failed'] };
  await browser.close();
  const bit = (teeth.problems || []).some((p) => p.startsWith('client_errors:'));
  console.log(`\n  teeth - the pre-fix logbook (${BASE}) under optional-fail: ${bit ? 'FAILS as it must' : 'DID NOT FAIL'} - ${(teeth.problems || []).join(' | ').slice(0, 200)}`);
  teeth.bit = bit;
}

mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify({ _doc: 'prove_page_survives_optional_failures.mjs - SL A3/AV1/H1 readings, one per (page, engine, condition)',
  generated: new Date().toISOString(), csp: LOCAL_CSP, base: BASE, results, teeth }, null, 1));
const bad = results.filter((r) => !r.ok);
console.log(`\n${results.length} reading(s), ${bad.length} failing; written to ${OUT}`);
if (TEETH && !teeth.bit) { console.log('FAIL page-survives-optional-failures - NO TEETH: the pre-fix logbook did not fail'); process.exit(1); }
if (bad.length) { console.log(`FAIL page-survives-optional-failures - ${bad.length} reading(s)`); process.exit(1); }
console.log('PASS page-survives-optional-failures - every named page starts up in WebKit and Chromium under the shipped CSP, '
  + 'with every optional subsystem failing, and throws nothing into client_errors; the pre-fix logbook does');
