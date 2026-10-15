// prove_csp_exact.mjs - SL sub-layer S3 (2026-10-15): "The platform must name in this page's CSP exactly the origins
// it loads from, sockets included, and nothing more."
//
// TWO HALVES, because a policy fails two ways:
//   COVERS        every origin the page loads is named in the policy the deploy serves it, and the browser reports
//                 no violation (else production blocks it silently - csp-covers-what-ships records five such outages,
//                 each found by a person, never a check)
//   NOTHING MORE  every origin the policy names for this page has a basis: the page loaded it live, or a named file of
//                 its own code loads it in that directive (tools/build_csp_profiles.py writes the per-page policies
//                 and the basis for each origin); and no scheme wildcard (`https:` names every origin there is)
//
// The policy is read the way the deploy will serve it: `tools/serve_vercel_headers.py --resolve` applies vercel.json's
// own rules (every match, in order, later keys winning) - this prover never re-derives Vercel's matching. The page is
// loaded in Chromium with that policy (production's Supabase origins mapped to the local stack, as the H1 prover does),
// signed in as its S3 cast through the product's own form (a public page as the visitor it is for), settled, scrolled
// to the end (lazy images), and every request it makes is read by resource type into the directive that governs it.
//
//   node tools/prove_csp_exact.mjs --measure  [--page a.html,b.html] [--json .tmp/csp_exact_measure.json]
//   node tools/prove_csp_exact.mjs --verdict  [--page ...] [--json .tmp/csp_exact_results.json] [--policy-commit SHA]
// --policy-commit serves the vercel.json of that commit instead (the TEETH: the site-wide policy must fail NOTHING MORE).
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { SEEDER, stubModelCalls } from './prover_harness.mjs';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const VERDICT = process.argv.includes('--verdict');
const OUT = arg('--json', VERDICT ? '.tmp/csp_exact_results.json' : '.tmp/csp_exact_measure.json');
const COMMIT = arg('--policy-commit', null);
const PROD_HOST = 'hzyvnjtisfgbksicrouu.supabase.co';
const LOCAL = '127.0.0.1:54321';
const SELF_HOSTS = new Set(['localhost:5000', '127.0.0.1:5000']);
const WILDCARDS = new Set(['https:', 'http:', '*', 'wss:', 'ws:']);

const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const S3 = reg.trajectories.filter((t) => t.sl && t.sl.sublayer === 'S3' && t.status !== 'descoped');
const castOf = new Map(S3.map((t) => [t.sl.page, t.persona]));
const PAGES = arg('--page') ? arg('--page').split(',') : [...castOf.keys()];
const SUP = /supervisor|oversight|owner|engineer|manager/i;
const ACCOUNT = (persona) => persona === 'anon' ? { user: 'anon' } : (SUP.test(persona) ? { user: 'leandromarquez' } : { user: 'bryangarcia' });

// the policy the deploy serves each page, from the one matcher (python on PATH; no shell, so no path rewriting)
let root = '.';
if (COMMIT) {
  root = mkdtempSync(join(tmpdir(), 'csp-commit-'));
  writeFileSync(join(root, 'vercel.json'), execFileSync('git', ['show', `${COMMIT}:vercel.json`], { encoding: 'utf8' }));
}
const resolved = JSON.parse(execFileSync('python', ['tools/serve_vercel_headers.py', '--root', root, '--resolve', ...PAGES.map((p) => '/' + p)], { encoding: 'utf8', maxBuffer: 16 << 20 }));
const cspOf = (page) => (Object.entries(resolved['/' + page] || {}).find(([k]) => k.toLowerCase() === 'content-security-policy') || [])[1] || '';
const toLocal = (csp) => csp.replaceAll(`https://${PROD_HOST}`, `http://${LOCAL}`).replaceAll(`wss://${PROD_HOST}`, `ws://${LOCAL}`)
  .replace(/img-src ([^;]*)/, (m, v) => `img-src ${v} http://${LOCAL}`);
const parse = (csp) => Object.fromEntries(csp.split(';').map((p) => p.trim().split(/\s+/)).filter((b) => b[0]).map((b) => [b[0], b.slice(1)]));
// the basis for every origin each page's policy names (the generator's evidence), when judging
const PROFILES = VERDICT ? JSON.parse(execFileSync('python', ['tools/build_csp_profiles.py', '--json', '.tmp/csp_profiles.json'], { encoding: 'utf8', maxBuffer: 32 << 20 }) && readFileSync('.tmp/csp_profiles.json', 'utf8')) : {};

// resource type -> the directive that governs it (CSP3; a directive the policy omits falls back to default-src)
const DIRECTIVE = { script: 'script-src', stylesheet: 'style-src', font: 'font-src', image: 'img-src', media: 'media-src',
  fetch: 'connect-src', xhr: 'connect-src', eventsource: 'connect-src', websocket: 'connect-src', ping: 'connect-src',
  beacon: 'connect-src', document: 'frame-src', manifest: 'manifest-src', other: 'default-src', texttrack: 'media-src' };
// a request's origin as the PRODUCTION policy would name it (the local stack stands in for the Supabase project)
const prodOrigin = (u) => {
  let x; try { x = new URL(u); } catch (e) { return null; }
  if (x.protocol === 'data:' || x.protocol === 'blob:') return x.protocol;
  if (SELF_HOSTS.has(x.host)) return "'self'";
  if (x.host === LOCAL) return (x.protocol === 'ws:' ? 'wss://' : 'https://') + PROD_HOST;
  return `${x.protocol}//${x.host}`;
};

async function signIn(ctx, user) {
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/index.html?signin=1`, { waitUntil: 'load', timeout: 45000 });
  await p.fill('#si-username', user); await p.fill('#si-password', 'test1234'); await p.click('#si-btn');
  const ok = await p.waitForFunction(() => !!localStorage.getItem('wh_active_hive_id'), null, { timeout: 25000 }).then(() => true).catch(() => false);
  await p.close();
  return ok;
}

async function load(ctx, page) {
  const p = await ctx.newPage();
  const used = {}; const add = (dir, o) => { if (!o) return; (used[dir] = used[dir] || new Set()).add(o); };
  p.on('request', (r) => { if (r.isNavigationRequest() && r.frame() === p.mainFrame()) return; add(DIRECTIVE[r.resourceType()] || 'default-src', prodOrigin(r.url())); });
  p.on('websocket', (ws) => add('connect-src', prodOrigin(ws.url())));
  let loadError = null;
  await p.goto(`${SEEDER}/workhive/${page}`, { waitUntil: 'load', timeout: 60000 }).catch((e) => { loadError = String(e.message).slice(0, 120); });
  await p.waitForLoadState('networkidle', { timeout: 12000 }).catch(() => {});
  await p.waitForTimeout(3000);
  await p.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 700) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 120)); } }).catch(() => {});
  await p.waitForTimeout(1500);
  const st = await p.evaluate(() => ({ chars: (document.body.innerText || '').length, cspv: (window.__cspv || []).slice(0, 8), url: location.pathname.split('/').slice(-3).join('/') }))
    .catch((e) => ({ chars: 0, cspv: [], url: '?', err: String(e.message).slice(0, 100) }));
  await p.close();
  return { page, loadError, ...st, used: Object.fromEntries(Object.entries(used).map(([k, v]) => [k, [...v].sort()])) };
}

// the verdict for one page: covers + nothing more, against the policy it was SERVED
function judge(page, r) {
  const csp = cspOf(page); const pol = parse(csp); const problems = [];
  if (!csp) problems.push('no Content-Security-Policy resolved for the page');
  if (r.loadError) problems.push(`load: ${r.loadError}`);
  if ((r.cspv || []).length) problems.push(`CSP violation: ${r.cspv.join(' | ')}`);
  for (const [d, origins] of Object.entries(r.used || {})) {
    const srcs = pol[d] || pol['default-src'] || [];
    for (const o of origins) if (!srcs.includes(o) && !(o === "'self'" && srcs.includes("'self'"))) problems.push(`COVERS: loaded ${o} through ${d}, which the served policy does not name`);
  }
  const basis = (PROFILES[page] || {}).basis || {};
  const named = [];
  for (const [d, srcs] of Object.entries(pol)) {
    for (const s of srcs) {
      if (WILDCARDS.has(s)) { problems.push(`NOTHING MORE: ${d} names the scheme wildcard ${s} - every origin there is`); continue; }
      if (!s.includes('://')) continue;
      named.push(`${d} ${s}`);
      if (!basis[`${d} ${s}`]) problems.push(`NOTHING MORE: ${d} names ${s}, which this page neither loaded nor has code that loads it that way`);
    }
  }
  return { csp, named, basis: Object.fromEntries(named.map((k) => [k, basis[k] || null])), problems };
}

const byUser = new Map();
for (const page of PAGES) { const u = ACCOUNT(castOf.get(page) || 'anon').user; (byUser.get(u) || byUser.set(u, []).get(u)).push(page); }
const results = [];
for (const [user, pages] of byUser) {
  const browser = await chromium.launch({ args: ['--disable-features=LocalNetworkAccessChecks,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights'] });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });
  await stubModelCalls(ctx);
  await ctx.route('**/rest/v1/client_errors*', (r) => r.request().method() === 'POST' ? r.fulfill({ status: 201, contentType: 'application/json', body: '[]' }) : r.continue());
  await ctx.route(/\/workhive\/[^?]*\.html(\?.*)?$/, async (route) => {
    const file = new URL(route.request().url()).pathname.replace(/^\/workhive\//, '');
    const r = await route.fetch(); const body = await r.text();
    return route.fulfill({ status: r.status(), contentType: 'text/html; charset=utf-8', body, headers: { 'Content-Security-Policy': toLocal(cspOf(file) || cspOf('index.html')), 'Cache-Control': 'no-store' } });
  });
  await ctx.addInitScript(() => { window.__cspv = []; document.addEventListener('securitypolicyviolation', (e) => window.__cspv.push(`${e.violatedDirective} ${e.blockedURI}`)); });
  const ok = user === 'anon' ? true : await signIn(ctx, user);
  for (const page of pages) {
    const r = ok ? await load(ctx, page) : { page, loadError: `sign-in as ${user} failed - no reading taken` };
    const v = VERDICT ? judge(page, r) : { problems: [...(r.loadError ? [r.loadError] : []), ...((r.cspv || []).map((x) => 'CSP ' + x))] };
    results.push({ ...r, engine: 'chromium', condition: 'as-served', cast: castOf.get(page), account: user, ...v, ok: !v.problems.length });
    console.log(`  ${v.problems.length ? 'FAIL' : 'ok  '} ${page.padEnd(48)} ${String(r.chars ?? '-').padStart(6)}c  ${Object.entries(r.used || {}).map(([d, o]) => `${d.replace('-src', '')}:${o.length}`).join(' ')}`
      + (v.problems.length ? `\n         ${v.problems.slice(0, 4).join('\n         ')}` : ''));
  }
  await browser.close();
}
// TEETH: the same NOTHING MORE judgement, against the policy the last site-wide commit served every page. Each page
// must fail it - that policy's img-src named the scheme wildcard for all of them - or this prover cannot tell an exact
// policy from a union one, and it fails itself.
let teeth = null;
if (VERDICT && !COMMIT) {
  const TEETH_COMMIT = arg('--teeth-commit', 'a8ffe363');
  const troot = mkdtempSync(join(tmpdir(), 'csp-teeth-'));
  writeFileSync(join(troot, 'vercel.json'), execFileSync('git', ['show', `${TEETH_COMMIT}:vercel.json`], { encoding: 'utf8' }));
  const old = JSON.parse(execFileSync('python', ['tools/serve_vercel_headers.py', '--root', troot, '--resolve', ...PAGES.map((p) => '/' + p)], { encoding: 'utf8', maxBuffer: 16 << 20 }));
  const bad = [];
  for (const page of PAGES) {
    const csp = (Object.entries(old['/' + page] || {}).find(([k]) => k.toLowerCase() === 'content-security-policy') || [])[1] || '';
    const basis = (PROFILES[page] || {}).basis || {};
    const extra = [];
    for (const [d, srcs] of Object.entries(parse(csp))) for (const s of srcs) {
      if (WILDCARDS.has(s)) extra.push(`${d} ${s}`);
      else if (s.includes('://') && !basis[`${d} ${s}`]) extra.push(`${d} ${s}`);
    }
    if (extra.length) bad.push({ page, extra });
  }
  teeth = { commit: TEETH_COMMIT, pages: PAGES.length, failed: bad.length, bit: bad.length === PAGES.length,
    sample: bad.slice(0, 1).map((b) => `${b.page}: ${b.extra.slice(0, 4).join(', ')}`).join('') };
  console.log(`\n  teeth - under ${TEETH_COMMIT}'s site-wide policy ${bad.length}/${PAGES.length} page(s) name origins with no basis: ${teeth.bit ? 'FAILS as it must' : 'DID NOT FAIL on every page'} (${teeth.sample})`);
}
mkdirSync(dirname(OUT), { recursive: true });
const failed = results.filter((r) => !r.ok).length + (teeth && !teeth.bit ? 1 : 0);
writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), mode: VERDICT ? 'verdict' : 'measure', policy_commit: COMMIT, sublayer: 'S3', pages: results.length, failed, teeth, results }, null, 1));
console.log(`\n${VERDICT ? (failed ? 'FAIL' : 'PASS') : 'measured'} csp-exact - ${results.length - failed}/${results.length} page(s) clean${COMMIT ? ` under ${COMMIT}'s policy` : ''} -> ${OUT}`);
process.exit(VERDICT && failed ? 1 : 0);
