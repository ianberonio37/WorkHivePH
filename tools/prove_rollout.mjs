// prove_rollout.mjs - SL sub-layer H4 (2026-10-15): "The platform must roll this page out so a returning device moves
// to the new version within one visit, never half new and half old."
//
// A RETURNING DEVICE, built for real: a fresh browser profile (service worker allowed) visits the page while the origin
// serves the PREVIOUS build - the newest commit whose sw.js CACHE_NAME differs from the working tree's, served file by
// file from git by tools/serve_vercel_headers.py --ref - so the old worker installs, precaches its shell and keeps its
// copies, exactly as on a phone that opened the page last week. Then the SAME origin switches to the current build
// (the working tree) and the device comes back:
//   visit 1   the first visit after the deploy. Its document and every same-origin script it ran must come from ONE
//             build - all old (the worker's copy, replaced in the background) or all new - never new HTML on old
//             scripts or the reverse. A page that reloads itself onto the new build within the visit (the utils.js
//             skew heal) is read at its final document.
//   visit 2   the next visit: the document and every script that differs between the builds are the new build's
//   moved     by the end of visit 2 the device holds only the new build's cache (no old CACHE_NAME left behind)
// Only files that DIFFER between the two builds can show which build answered, so each verdict names how many it read.
// TEETH (every run): the same returning device against a planted rollout that serves the NEW page with the OLD
// scripts - a half-new page by construction - must be caught as mixed.
//
//   node tools/prove_rollout.mjs [--pages a.html,b.html] [--from <sha>] [--json .tmp/rollout_results.json]
import { chromium } from 'playwright';
import { spawn, execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { takeBrowserSlot } from './browser_slot.mjs';

const arg = (k) => { const i = process.argv.indexOf(k); return i >= 0 ? process.argv[i + 1] : null; };
const PORT = 5077, ORIGIN = `http://127.0.0.1:${PORT}`;
const OUT = arg('--json') || '.tmp/rollout_results.json';
const sh = (args) => execFileSync('git', args, { encoding: 'utf8', maxBuffer: 64 << 20 }).trim();
const blobAt = (ref, rel) => { try { return execFileSync('git', ['cat-file', 'blob', `${ref}:${rel}`], { maxBuffer: 64 << 20 }); } catch (e) { return null; } };
const sha = (buf) => createHash('sha256').update(buf).digest('hex').slice(0, 16);
const cacheName = (txt) => (String(txt).match(/^const CACHE_NAME\s*=\s*'([^']+)'/m) || [])[1];
const NOW_CACHE = cacheName(readFileSync('sw.js', 'utf8'));
const FROM = arg('--from') || (() => {
  for (const c of sh(['rev-list', '--max-count=40', 'HEAD']).split('\n')) {
    const b = blobAt(c, 'sw.js');
    if (b && cacheName(b.toString('utf8')) !== NOW_CACHE) return c.slice(0, 8);
  }
  throw new Error('no commit in the last 40 has a different CACHE_NAME');
})();
const OLD_CACHE = cacheName(blobAt(FROM, 'sw.js').toString('utf8'));
const REG = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
const H4 = new Map();
for (const t of REG.trajectories) if (t.sl && t.sl.sublayer === 'H4' && t.status !== 'descoped') H4.set(t.sl.page, t);
const PAGES = (arg('--pages') ? arg('--pages').split(',') : [...H4.keys()].sort()).filter((f) => existsSync(f));

// ── the origin: one port, two builds ──
let srv = null;
const serve = async (ref) => {
  if (srv) { srv.kill(); await new Promise((r) => srv.once('exit', r)); srv = null; }
  srv = spawn(process.platform === 'win32' ? 'python' : 'python3',
    ['tools/serve_vercel_headers.py', '--port', String(PORT), '--local-supabase', ...(ref ? ['--ref', ref] : [])], { stdio: 'ignore' });
  for (let i = 0; i < 40; i++) { try { const r = await fetch(`${ORIGIN}/sw.js`); if (r.ok) return; } catch (e) { void e; } await new Promise((r) => setTimeout(r, 250)); }
  throw new Error('the local origin did not come up');
};
const relOf = (url) => { const u = new URL(url); if (u.origin !== ORIGIN) return null; let p = decodeURIComponent(u.pathname).replace(/^\//, '');
  if (!p || p.endsWith('/')) p += 'index.html'; else if (!/\.[a-z0-9]+$/i.test(p)) p += '/index.html'; return p; };
const SIG = new Map();   // rel -> { old, now } content hashes (null = absent in that build)
const sigOf = (rel) => { if (!SIG.has(rel)) { const o = blobAt(FROM, rel); SIG.set(rel, { old: o ? sha(o) : null, now: existsSync(rel) ? sha(readFileSync(rel)) : null }); } return SIG.get(rel); };
const buildOf = (rel, body) => { const s = sigOf(rel), h = sha(body); if (s.old === s.now) return 'same'; return h === s.now ? 'new' : h === s.old ? 'old' : 'other'; };

// one visit: the final document and the scripts it ran, each labelled with the build that answered
async function visit(page, url) {
  const seen = [];
  const onResp = async (r) => { const req = r.request(); const rel = relOf(r.url());
    if (!rel || !/^(document|script)$/.test(req.resourceType()) || (req.resourceType() === 'document' && req.frame() !== page.mainFrame())) return;
    try { const body = await r.body(); seen.push({ rel, type: req.resourceType(), build: buildOf(rel, body), sw: r.fromServiceWorker(), at: Date.now() }); } catch (e) { void e; } };
  page.on('response', onResp);
  await page.goto(url, { waitUntil: 'load', timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(6000);             // a self-heal reload lands inside this
  page.off('response', onResp);
  const docs = seen.filter((s) => s.type === 'document');
  const last = docs[docs.length - 1];
  const after = last ? seen.filter((s) => s.at >= last.at) : seen;
  const scripts = after.filter((s) => s.type === 'script');
  const informative = [last, ...scripts].filter((s) => s && /^(old|new|other)$/.test(s.build));
  const builds = [...new Set(informative.map((s) => s.build))];
  return { reloads: Math.max(0, docs.length - 1), doc: last ? last.build : 'none', docFromWorker: last ? last.sw : null,
    scripts: scripts.length, informative: informative.length, builds,
    mixed: builds.length > 1 ? informative.map((s) => `${s.rel}=${s.build}${s.sw ? '(worker)' : ''}`).slice(0, 8) : [] };
}

async function returningDevice(browser, file, newRef) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });   // service workers allowed
  const page = await ctx.newPage();
  const url = `${ORIGIN}/${file}`;
  await serve(FROM);
  await page.goto(url, { waitUntil: 'load', timeout: 45000 }).catch(() => {});
  await page.evaluate(() => navigator.serviceWorker && navigator.serviceWorker.ready).catch(() => {});
  await page.waitForTimeout(1500);
  await page.reload({ waitUntil: 'load' }).catch(() => {});      // now controlled: the old worker keeps its copies
  await page.waitForTimeout(2500);
  const oldState = await page.evaluate(async () => ({ controlled: !!navigator.serviceWorker.controller, caches: await caches.keys() })).catch(() => ({}));
  await serve(newRef);
  const v1 = await visit(page, url);
  const v2 = await visit(page, url);
  const caches = await page.evaluate(async () => caches.keys()).catch(() => []);
  await ctx.close();
  return { oldState, v1, v2, caches };
}

function judge(r) {
  const problems = [];
  if (!r.oldState.controlled) problems.push('the old build\'s worker never controlled the page (no returning device to test)');
  if (r.v1.mixed.length) problems.push(`visit 1 was half new and half old: ${r.v1.mixed.join(', ')}`);
  if (r.v2.doc === 'old' || r.v2.builds.includes('old') || r.v2.builds.includes('other')) problems.push(`visit 2 still ran the old build (${r.v2.mixed.join(', ') || 'document ' + r.v2.doc})`);
  if (r.caches.includes(OLD_CACHE)) problems.push(`the device still holds ${OLD_CACHE} after two visits`);
  if (!r.caches.includes(NOW_CACHE)) problems.push(`the device never cached ${NOW_CACHE}`);
  return problems;
}

await takeBrowserSlot('rollout');
const browser = await chromium.launch();
console.log(`  returning device: ${FROM} (${OLD_CACHE}) -> the working tree (${NOW_CACHE})`);
// TEETH: the new build's page with one shared script forced to its OLD bytes is half new by construction; visit() must
// call it mixed.
let teeth = { bit: false };
{
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  const probe = PAGES.find((p) => { const s = sigOf(p); return s.old !== s.now; }) || PAGES[0];
  const oldScript = ['utils.js', 'nav-hub.js', 'wayfinding.js', 'learn-link.js'].find((s) => { const g = sigOf(s); return g.old && g.now && g.old !== g.now; });
  await serve(null);
  if (oldScript) await ctx.route(`${ORIGIN}/${oldScript}*`, (r) => r.fulfill({ status: 200, contentType: 'application/javascript', body: blobAt(FROM, oldScript) }));
  const v = await visit(page, `${ORIGIN}/${probe}`);
  teeth = { page: probe, planted: oldScript, mixed: v.mixed, bit: !!oldScript && v.mixed.length > 0 };
  await ctx.close();
  console.log(`  teeth - ${probe} served new with an OLD ${oldScript}: ${teeth.bit ? 'CAUGHT as half new and half old' : 'NOT CAUGHT'}`);
}
const results = [];
for (const file of PAGES) {
  let r, problems;
  try { r = await returningDevice(browser, file, null); problems = judge(r); }
  catch (e) { r = { error: String(e && e.message || e).slice(0, 160) }; problems = ['not read: ' + r.error]; }
  results.push({ page: file, cast: (H4.get(file) || {}).persona, engine: 'chromium', condition: 'returning-device', from: FROM, ...r, problems, ok: !problems.length });
  console.log(`  ${problems.length ? 'open' : 'ok  '} ${file.padEnd(58)} ${problems.length ? problems.join('; ').slice(0, 200)
    : `v1 ${r.v1.builds.join('/') || 'same'}${r.v1.reloads ? ' after ' + r.v1.reloads + ' reload' : ''} (${r.v1.informative} read), v2 ${r.v2.builds.join('/') || 'same'}, caches ${r.caches.join(',')}`}`);
}
if (srv) srv.kill();
await browser.close();
mkdirSync('.tmp', { recursive: true });
writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), sublayer: 'H4', from: FROM, old_cache: OLD_CACHE, now_cache: NOW_CACHE,
  runs: { rollout: new Date().toISOString() }, teeth, results }, null, 1) + '\n');
const bad = results.filter((r) => !r.ok).length;
console.log(`\n${bad || !teeth.bit ? 'FAIL' : 'PASS'} rollout - ${results.length - bad}/${results.length} page(s) move a returning device to the new build within one visit, never half new and half old -> ${OUT}`);
process.exit(bad || !teeth.bit ? 1 : 0);
