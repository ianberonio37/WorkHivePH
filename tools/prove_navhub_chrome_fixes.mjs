// prove_navhub_chrome_fixes.mjs - TEETH for two wave-4 nav-hub chrome fixes (2026-09-14), synthetic + light.
//
// The 30-host nav-hub ratchet is not viable on this 8 GB host; these two fixes are verifiable on a single
// synthetic headless page each, with a NEGATIVE control proving the test would catch a regression:
//
//   W41441 report-sender report-tabs - two role=tab chips in a flex-wrap:nowrap overflow-x:auto strip wrapped to
//           2 lines at 390 because they had default flex-shrink. With flex-shrink:0 + white-space:nowrap each is
//           ONE line. Test: at 390, the fixed chips render single-line; the unfixed (shrinkable) control wraps.
//   W41384 wayfinding pill vs a page's OWN back control - a page that ships a .back-link must make wayfinding.js
//           SKIP its floating pill (line-180 path), so it never stacks a second back control on the page's own.
//           Test: with a .back-link present, wayfinding injects NO #wh-wayfinding; without one, it DOES.
//
//   node tools/prove_navhub_chrome_fixes.mjs
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';

const WAYFINDING = readFileSync('wayfinding.js', 'utf8');
const HEAD = '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width"><title>Synthetic · WorkHive</title><style>body{margin:0;font-family:sans-serif}</style></head><body>';

// the report-sender strip, faithful to report-sender.html: flex-wrap:nowrap, overflow-x:auto; each tab
// inline-flex with the fix (flex-shrink:0; white-space:nowrap). A third, deliberately SHRINKABLE control is the
// negative control - it must wrap where the fixed ones do not.
const TABS = HEAD
  + '<main style="width:390px"><div style="display:flex; gap:8px; flex-wrap:nowrap; overflow-x:auto; width:390px">'
  + '<a id="t1" role="tab" style="padding:6px 12px; min-height:34px; display:inline-flex; align-items:center; font-size:.76rem; flex-shrink:0; white-space:nowrap;">&larr; Analytics report</a>'
  + '<span id="t2" role="tab" style="padding:6px 12px; min-height:34px; display:inline-flex; align-items:center; font-size:.76rem; flex-shrink:0; white-space:nowrap;">Send / schedule</span>'
  + '<span id="t3neg" role="tab" style="padding:6px 12px; min-height:34px; display:inline-flex; align-items:center; font-size:.76rem;">Send or schedule this analytics report to the whole distribution list every morning (negative control, shrinkable)</span>'
  + '</div></main></body></html>';

const owns = (backLink) => HEAD + '<main><h1>A page that owns its back</h1>'
  + (backLink ? '<button class="back-link" onclick="void 0">&larr; Setup</button>' : '<button onclick="void 0">&larr; Setup</button>')
  + '<p>content</p></main></body></html>';

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
const fails = [];

// ── W41441: the fixed tabs are single-line; the unfixed negative control wraps ──
await page.setContent(TABS, { waitUntil: 'load' });
const tabs = await page.evaluate(() => {
  // count TEXT lines via Range client rects (the flex row's align-items:stretch makes box height useless -
  // every item stretches to the tallest, so a one-line tab reports the wrapped tab's height). This is the
  // same measure phone_fit_audit uses for a wrapped control label.
  const lines = (id) => {
    const el = document.getElementById(id); const rg = document.createRange(); rg.selectNodeContents(el);
    const rects = [...rg.getClientRects()].filter((q) => q.width > 0 && q.height > 0).sort((a, b) => a.top - b.top);
    let n = 0, bottom = -1e9;
    for (const q of rects) { if (q.top >= bottom - 2) { n++; bottom = q.bottom; } else bottom = Math.max(bottom, q.bottom); }
    return n;
  };
  return { t1: lines('t1'), t2: lines('t2'), neg: lines('t3neg') };
});
// Teeth: the two FIXED tabs (flex-shrink:0 + white-space:nowrap) render ONE text line; the shrinkable negative
// control wraps to MORE than one, proving the fix is what keeps the labels on one line.
if (tabs.t1 !== 1) fails.push(`report-tab 1 must be ONE text line (flex-shrink:0 + nowrap) - got ${tabs.t1} lines`);
if (tabs.t2 !== 1) fails.push(`report-tab 2 must be ONE text line (flex-shrink:0 + nowrap) - got ${tabs.t2} lines`);
if (tabs.neg < 2) fails.push(`the shrinkable negative control should WRAP to 2+ lines, or the test has no teeth - got ${tabs.neg} line(s)`);

// ── W41384: a .back-link makes wayfinding SKIP its pill; without one it injects it ──
async function pillInjected(html) {
  await page.setContent(html, { waitUntil: 'load' });
  await page.evaluate((src) => { delete window.__whWayfinding; (0, eval)(src); }, WAYFINDING);
  await page.waitForTimeout(50);
  return page.evaluate(() => !!document.getElementById('wh-wayfinding'));
}
const withBack = await pillInjected(owns(true));
const withoutBack = await pillInjected(owns(false));
if (withBack) fails.push('a page with its own .back-link must make wayfinding SKIP the pill (W41384) - but #wh-wayfinding was injected');
if (!withoutBack) fails.push('the negative control (no back affordance) should get the pill, or the test has no teeth - #wh-wayfinding was NOT injected');

await b.close();
if (fails.length) {
  console.log('FAIL navhub-chrome-fixes - ' + fails.join(' | '));
  process.exit(1);
}
console.log(`PASS navhub-chrome-fixes - report tabs hold ONE text line at 390 (fixed ${tabs.t1}/${tabs.t2} line vs unfixed ${tabs.neg} lines), and a page's own .back-link makes wayfinding skip its pill (present without one)`);
