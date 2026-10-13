// prove_realtime_blocked_socket.mjs - a blocked realtime socket must never stop a page from loading, and the
// production CSP must let WebKit open the socket at all (gate `realtime-blocked-socket`, 2026-10-14).
//
// WHY. Ian, 2026-10-14: "the concern and issues that I had about the logbook list and registered assets are still
// there ... it can be found to asset hub, but no list in my manage assets and select assets." Production's
// client_errors held the answer his phone had been writing on every visit: "WebSocket not available: The operation
// is insecure." thrown from subscribeLogbookRealtime() inside the logbook's async start-up, BEFORE initAssets().
// WebKit (iPhone Chrome and Safari) throws SecurityError from `new WebSocket` when the CSP's connect-src does not
// name wss: - and vercel.json named only https://hzyvnjtisfgbksicrouu.supabase.co. Chromium fails such a socket
// quietly, which is why every local walk passed. Two things are proven here, each with teeth:
//   1. CSP SEMANTICS, in real WebKit: under the OLD connect-src a wss: WebSocket to the Supabase host THROWS
//      SecurityError; under the connect-src vercel.json ships now it does not; and vercel.json really names wss:.
//   2. THE START-UP SURVIVES: with `new WebSocket` forced to throw (the WebKit behaviour, in Chromium), the logbook
//      opened as a hive supervisor still loads its assets (the fix in utils.js + logbook.html); served the PRE-FIX
//      utils.js and logbook.html from git, the same walk ends with no assets - so the guard is what makes it pass.
//
//   node tools/prove_realtime_blocked_socket.mjs
import { chromium, webkit } from 'playwright';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { SEEDER } from './prover_harness.mjs';

const WHO = { username: 'leandromarquez', password: 'test1234' };   // a hive supervisor with approved hive assets
const HOST = 'hzyvnjtisfgbksicrouu.supabase.co';
const vercel = JSON.parse(readFileSync('vercel.json', 'utf8'));
const shippedCsp = (vercel.headers || []).flatMap((h) => h.headers || []).find((h) => /content-security-policy/i.test(h.key))?.value || '';
// the OLD production value is the shipped one minus the wss: entry - the same script-src, so the test script itself
// runs under both (a stricter synthetic CSP blocked the inline test script and read as 'no result', 2026-10-14)
const OLD_CSP = shippedCsp.replace(` wss://${HOST}`, '');
const problems = [];
const notes = [];

// ── 1. CSP semantics in WebKit ───────────────────────────────────────────────────────────────────────────────
async function webkitSocket(csp) {
  const b = await webkit.launch();
  const page = await (await b.newContext()).newPage();
  await page.route('https://csp.test/**', (route) => route.fulfill({
    status: 200, contentType: 'text/html',
    headers: { 'Content-Security-Policy': csp },
    body: `<!doctype html><title>csp</title><script>
      try { new WebSocket('wss://${HOST}/realtime/v1/websocket?vsn=1.0.0'); window.__r = 'constructed'; }
      catch (e) { window.__r = 'threw:' + e.name + ':' + e.message; }
    </script>`,
  }));
  await page.goto('https://csp.test/p.html', { waitUntil: 'load', timeout: 30000 });
  const r = await page.evaluate(() => window.__r || 'no result');
  await b.close();
  return r;
}
const underOld = await webkitSocket(OLD_CSP);
const underShipped = await webkitSocket(shippedCsp.replace(/frame-ancestors[^;]*;?/i, ''));
notes.push(`WebKit, old connect-src (https only): ${underOld}`);
notes.push(`WebKit, the connect-src vercel.json ships: ${underShipped}`);
if (!/^threw:SecurityError/.test(underOld)) problems.push(`VACUOUS: WebKit did not throw under the old CSP (${underOld}), so this proof cannot tell the fix from no fix`);
if (underShipped !== 'constructed') problems.push(`WebKit still cannot open the Supabase socket under the shipped CSP (${underShipped})`);
if (!new RegExp(`connect-src[^;]*\\bwss://${HOST.replace(/\./g, '\\.')}`).test(shippedCsp)) problems.push('vercel.json connect-src does not name wss://' + HOST);

// ── 2. The start-up survives a throwing socket ───────────────────────────────────────────────────────────────
async function logbookWithThrowingSocket(prefix) {
  const ctx = await chromium.launch().then((b) => b.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' }).then((c) => ({ b, c })));
  const { b, c } = ctx;
  if (prefix) {   // the pre-fix files, from git
    const oldUtils = execFileSync('git', ['show', `${prefix}:utils.js`], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
    const oldLogbook = execFileSync('git', ['show', `${prefix}:logbook.html`], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
    await c.route('**/utils.js*', (r) => r.fulfill({ status: 200, contentType: 'application/javascript', body: oldUtils }));
    await c.route('**/logbook.html*', (r) => r.fulfill({ status: 200, contentType: 'text/html', body: oldLogbook }));
  }
  // the WebKit behaviour, reproduced in Chromium: a CSP-blocked socket throws SecurityError at construction
  await c.addInitScript(() => { window.WebSocket = function () { throw new DOMException('The operation is insecure.', 'SecurityError'); }; });
  const page = await c.newPage();
  await page.goto(`${SEEDER}/workhive/index.html?signin=1`, { waitUntil: 'load', timeout: 30000 });
  await page.fill('#si-username', WHO.username);
  await page.fill('#si-password', WHO.password);
  await page.click('#si-btn');
  await page.waitForFunction(() => !!localStorage.getItem('wh_active_hive_id'), null, { timeout: 20000 }).catch(() => {});
  await page.goto(`${SEEDER}/workhive/logbook.html`, { waitUntil: 'load', timeout: 45000 });
  let st = { hive: null, assets: null };
  for (let i = 0; i < 20; i++) {
    await page.waitForTimeout(1000);
    st = await page.evaluate(() => ({
      hive: (typeof HIVE_ID !== 'undefined') ? HIVE_ID : 'undeclared',
      assets: (typeof _assets !== 'undefined' && Array.isArray(_assets)) ? _assets.length : null,
    })).catch(() => st);
    if (st.assets > 0) break;
  }
  await b.close();
  return st;
}
const fixed = await logbookWithThrowingSocket(null);
notes.push(`logbook with a throwing WebSocket, current files: hive ${fixed.hive ? 'set' : 'none'}, assets ${fixed.assets}`);
if (!(fixed.assets > 0)) problems.push(`the logbook still loads no assets when the realtime socket throws (assets=${fixed.assets}) - the start-up is still dying on the live badge`);
const base = process.env.WH_PREFIX_BASE || '90ed9a8e';   // the last commit before this fix
const bare = await logbookWithThrowingSocket(base);
notes.push(`teeth, pre-fix utils.js + logbook.html (${base}): assets ${bare.assets} (null = the start-up died before the list existed)`);
if (bare.assets > 0) problems.push(`NO TEETH: the pre-fix files also loaded ${bare.assets} assets under a throwing socket, so this walk does not prove the guard`);

console.log('\nREALTIME · a blocked socket never stops a page from loading');
console.log('='.repeat(78));
for (const n of notes) console.log(`  ${n}`);
if (problems.length) {
  console.log('\n  FINDINGS:');
  for (const p of problems) console.log(`    - ${p}`);
  console.log(`\nFAIL realtime-blocked-socket - ${problems.length} finding(s)`);
  process.exit(1);
}
console.log('\nPASS realtime-blocked-socket - WebKit throws under the old CSP and opens the socket under the shipped one; with the socket '
  + 'throwing, the logbook still loads its assets, and the pre-fix files do not');
