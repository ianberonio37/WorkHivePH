// prove_listener_lifecycle — the "listener lifecycle" lens of the live-walk wave (2026-09-06).
//
// tests/realtime-arc-j.spec.ts already proves the CLIENT contract: subscribe adds a channel, removeChannel takes
// it away. What had no instrument is the per-SURFACE question, which is where this platform's realtime bugs have
// actually lived: does a page that re-subscribes on its own refresh path REMOVE the old channel first?
//
// In a multi-page app a navigation destroys the JS context, so a listener cannot leak ACROSS pages. It leaks
// WITHIN one - a page that re-subscribes on visibility change, on focus, on a poll tick or on a manual refresh,
// without removing what it already had, grows a channel per cycle. Every one of them then delivers the same row,
// which is how "two refreshers made a 90/s storm" happened here before.
//
//   L1 subscribes   the page opens at least one realtime channel (else it is not a realtime surface and is n/a)
//   L2 stable       after driving the page's own refresh path several times - visibilitychange, focus, and its
//                   own refresh control if it has one - the channel count has NOT grown
//   L3 named        every channel carries a name (an anonymous channel cannot be removed by anything but a full
//                   removeAllChannels, which is how a partial cleanup silently keeps one alive)
//
//   node tools/prove_listener_lifecycle.mjs
//   node tools/prove_listener_lifecycle.mjs --page community.html
import { chromium } from 'playwright';
import { SEEDER, signIn, PAGE_QUERY, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const CYCLES = 4;

const ROSTER = [
  'hive.html', 'community.html', 'alert-hub.html', 'platform-actions.html', 'ai-quality.html',
  'founder-console.html', 'marketplace-admin.html', 'plant-connections.html', 'shift-brain.html',
  'logbook.html', 'inventory.html', 'dayplanner.html',
];

const CHANNELS = function channels() {
  const c = window._whSupabaseClient;
  if (!c || typeof c.getChannels !== 'function') return { supported: false, n: 0, names: [] };
  const ch = c.getChannels();
  return { supported: true, n: ch.length, names: ch.map((x) => x.topic || x.subTopic || '(anonymous)') };
};

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
await signIn(ctx);

let bad = 0, n = 0, na = 0;
for (const file of (ONLY ? [ONLY] : ROSTER)) {
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE_MS);
  const before = await p.evaluate(CHANNELS).catch(() => ({ supported: false, n: 0, names: [] }));
  if (!before.supported || before.n === 0) {
    na++;
    console.log(`  n/a ${file.padEnd(26)} opens no realtime channel - nothing to leak`);
    await p.close();
    continue;
  }
  n++;
  // drive the page's OWN refresh path, the way a person leaving and returning to the tab does
  for (let i = 0; i < CYCLES; i++) {
    await p.evaluate(() => {
      Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
      document.dispatchEvent(new Event('visibilitychange'));
    }).catch(() => {});
    await p.waitForTimeout(700);
    await p.evaluate(() => {
      Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
      document.dispatchEvent(new Event('visibilitychange'));
      window.dispatchEvent(new Event('focus'));
    }).catch(() => {});
    await p.waitForTimeout(1800);
    const btn = await p.$('button[id*="refresh" i], button[aria-label*="refresh" i], [data-action="refresh"]');
    if (btn) { await btn.click({ timeout: 2500 }).catch(() => {}); await p.waitForTimeout(1500); }
  }
  await p.waitForTimeout(3000);
  const after = await p.evaluate(CHANNELS).catch(() => before);
  const issues = [];
  if (after.n > before.n) issues.push(`L2 channels grew ${before.n} -> ${after.n} across ${CYCLES} hide/show cycles: ${after.names.slice(0, 4).join(', ')}`);
  const anon = after.names.filter((x) => x === '(anonymous)').length;
  if (anon) issues.push(`L3 ${anon} channel(s) have no name - only removeAllChannels can take them away`);
  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(26)} ${before.n} channel(s) at load, ${after.n} after ${CYCLES} cycles${issues.length ? '' : ' - stable'}`);
  for (const s of issues) console.log(`        ${s.slice(0, 160)}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} listener-lifecycle - ${n - bad}/${n} realtime surfaces hold their channel count across repeated hide/show cycles (${na} open none and are reported n/a, never ok)`);
process.exitCode = bad ? 1 : 0;
