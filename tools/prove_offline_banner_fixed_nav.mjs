// prove_offline_banner_fixed_nav.mjs - TEETH for the W41399 offline-banner fix (ledger C12, 2026-09-14).
//
// The offline banner is a full-width position:fixed strip at top:0 z-9999. v386 pushed the IN-FLOW body down by
// the banner's height, but a page's own <nav class="fixed top-0"> (hive.html:428 and every page on the shared
// Tailwind header) is position:fixed and does not move - so its Back link sat UNDER the banner exactly when a
// person is offline (the serial nav-hub walk: elementFromPoint at hive's "Back" @20,6 returned .wh-offline-banner).
// The fix in offline-banner.js: while the banner is open, `nav.fixed` / `header.fixed` drop by
// --wh-offline-banner-h (the v385 wayfinding rule, platform-wide). hive.html itself crashes this 8 GB host's
// headless renderer at page load, so the REAL-PAGE verification is host-blocked; this synthetic page verifies the
// MECHANISM, with a control, on a page the host can render:
//
//   before offline  - the fixed nav sits at top 0 and its Back link is reachable at its own centre (control)
//   after offline   - the banner shows; the nav's top MUST equal the banner's height (it dropped below the strip),
//                     and elementFromPoint at the Back link's centre MUST be the link, NOT the banner
//
// Tailwind's `top-0` is a CLASS rule (not inline) on the real pages, so the synthetic nav uses class-based
// positioning too - an inline top:0 would out-rank the fix and test nothing.
//
//   node tools/prove_offline_banner_fixed_nav.mjs
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';

const BANNER_JS = readFileSync('offline-banner.js', 'utf8');
const PAGE = '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width">'
  + '<style>body{margin:0;font-family:sans-serif}.fixed{position:fixed}.top-0{top:0}'
  + 'nav.fixed{left:0;right:0;height:56px;background:#162032;z-index:30}</style></head><body>'
  + '<nav class="fixed top-0"><a id="back" href="index.html" style="display:inline-flex;align-items:center;min-height:44px;padding:0 16px;color:#fff">&larr; Back</a></nav>'
  + '<main style="padding-top:72px"><h1>Board</h1><p>content under a fixed header</p></main></body></html>';

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
const fails = [];

await page.setContent(PAGE, { waitUntil: 'load' });
await page.addScriptTag({ content: BANNER_JS });

const measure = () => page.evaluate(() => {
  const nav = document.querySelector('nav.fixed'); const back = document.getElementById('back');
  const r = back.getBoundingClientRect(); const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  const banner = document.querySelector('.wh-offline-banner');
  return { navTop: Math.round(nav.getBoundingClientRect().top), backTop: Math.round(r.top),
    hitIsBack: !!hit && (hit === back || back.contains(hit)), hitName: hit ? (hit.id ? '#' + hit.id : hit.className || hit.tagName) : null,
    bannerH: banner && banner.classList.contains('show') ? Math.round(banner.getBoundingClientRect().height) : 0,
    varH: getComputedStyle(document.documentElement).getPropertyValue('--wh-offline-banner-h').trim() };
});

const before = await measure();
if (before.navTop !== 0) fails.push(`control: before offline the fixed nav must sit at top 0 - got ${before.navTop}`);
if (!before.hitIsBack) fails.push(`control: before offline the Back link must be reachable at its centre - hit ${before.hitName}`);

// go offline: the banner shows, publishes --wh-offline-banner-h, and marks html.wh-offline-banner-open
await page.evaluate(() => window.dispatchEvent(new Event('offline')));
await page.waitForTimeout(450);
const after = await measure();
if (!(after.bannerH > 0)) fails.push(`the banner did not show (height ${after.bannerH})`);
if (after.navTop < after.bannerH - 1) fails.push(`the fixed nav did NOT drop below the banner - nav top ${after.navTop}, banner ${after.bannerH}px (W41399 fix missing)`);
if (!after.hitIsBack) fails.push(`the Back link is still covered while offline - elementFromPoint returned ${after.hitName}`);

await b.close();
if (fails.length) {
  console.log('FAIL offline-banner-fixed-nav - ' + fails.join(' | '));
  process.exit(1);
}
console.log(`PASS offline-banner-fixed-nav - while offline the ${after.bannerH}px banner shows and the fixed nav drops to top ${after.navTop} (var ${after.varH}); its Back link is reachable at its centre (control: top 0 and reachable before)`);
