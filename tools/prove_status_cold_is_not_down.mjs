/**
 * Does the status page tell a cold start apart from an outage? (T198, 2026-08-28)
 *
 * status.html probes ten edge functions' /health with an 8s budget. It classified a TIMEOUT as
 * 'down' — and utils.js sets its own default budget to 30s precisely because that is the
 * documented edge cold-start allowance. So the most likely cause of a timeout on this page is a
 * perfectly healthy function that has not run recently, and the page whose entire job is telling
 * people whether the platform is up was publishing that as "DOWN" in red.
 *
 * MEASURED, before and after, with one function hung and one genuinely 503:
 *   before:  8/10 probed surfaces healthy (80%) · 2 DOWN
 *            ai-gateway -> "DOWN · HTTP 0 · 8018 ms · AbortError: signal is aborted without reason"
 *   after:   8/9 probed surfaces healthy (89%) · 1 DOWN · 1 did not answer in time (not counted either way)
 *            ai-gateway -> "no answer in 8s (may be cold-starting)"
 * Three things wrong in that one line: an outage asserted that nobody observed, a raw internal
 * abort string on a user-facing trust surface, and an availability percentage whose denominator
 * counted a surface the probe never actually read.
 *
 * ★IT ASSERTS ALL THREE STATES AT ONCE, on purpose. A gate that only checked the timeout case
 * would pass on a page that had stopped reporting genuine outages entirely — the cheapest way to
 * make "no false DOWN" true is to never say DOWN. So a real 503 must still read DOWN in the same
 * run that a hang reads as silence, and a healthy function must still read healthy.
 *
 * USAGE:  node tools/prove_status_cold_is_not_down.mjs
 * Exit 1 on any failed assertion.
 */
import { chromium } from 'playwright';

const B = process.env.WH_BASE || 'http://127.0.0.1:5000/workhive';
const fails = [];
const check = (ok, what, got) => {
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${what}${ok ? '' : `  (got: ${got})`}`);
  if (!ok) fails.push(what);
};

console.log('status-cold-is-not-down - is silence reported as silence, or as an outage?\n');

const browser = await chromium.launch();
const ctx = await browser.newContext({ serviceWorkers: 'block' });
const page = await ctx.newPage();

await ctx.route('**/functions/v1/**/health', async (route) => {
  const u = route.request().url();
  if (u.includes('ai-gateway')) return;                    // hangs -> the probe aborts at 8s
  if (u.includes('platform-gateway')) return route.fulfill({ status: 503, body: 'boom' });
  return route.fulfill({ status: 200, contentType: 'application/json',
                         body: JSON.stringify({ ok: true, deps: [] }) });
});

await page.goto(`${B}/status.html`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(11000);

const r = await page.evaluate(() => {
  const cards = Array.from(document.querySelectorAll('.card')).map((c) => ({
    fn: (c.querySelector('.fn span') || {}).textContent,
    cls: c.className.replace('card', '').trim(),
    meta: ((c.querySelector('.meta') || {}).textContent || '').trim(),
  }));
  return { summary: ((document.getElementById('summary') || {}).textContent || '').trim(),
           cold: cards.find((c) => c.fn === 'ai-gateway'),
           dead: cards.find((c) => c.fn === 'platform-gateway'),
           healthy: cards.find((c) => c.fn === 'embed-entry') };
});
await browser.close();

check(!!r.cold && r.cold.cls === 'timeout', 'a hung function reads as silence, not DOWN',
      r.cold ? r.cold.cls : 'card missing');
check(!!r.cold && !/DOWN/.test(r.cold.meta), 'the hung card does not say DOWN', r.cold && r.cold.meta);
check(!!r.cold && /cold-starting/i.test(r.cold.meta), 'it names the likely cause',
      r.cold && r.cold.meta);
check(!!r.cold && !/AbortError|signal is aborted/.test(r.cold.meta),
      'no raw internal abort text reaches the reader', r.cold && r.cold.meta);
// the other half: the page must still be capable of reporting a real outage
check(!!r.dead && r.dead.cls === 'down' && /DOWN/.test(r.dead.meta),
      'a real 503 still reads DOWN', r.dead ? `${r.dead.cls} / ${r.dead.meta}` : 'card missing');
check(!!r.healthy && r.healthy.cls === 'ok', 'a healthy function still reads healthy',
      r.healthy ? r.healthy.cls : 'card missing');
// and the counting must not quietly absorb it either way
check(/1 DOWN/.test(r.summary), 'exactly one surface is counted DOWN', r.summary);
check(/did not answer in time/.test(r.summary), 'the unanswered probe is named in the summary', r.summary);
check(/8\/9/.test(r.summary), 'the timed-out surface leaves the denominator', r.summary);

console.log(`\n  summary line: "${r.summary}"`);
console.log(`  ${fails.length ? `FAIL: ${fails.length} assertion(s)` : 'PASS: silence, outage and health are three different claims'}`);
process.exit(fails.length ? 1 : 0);
