/* prove_search_button_is_not_dead.mjs — T78: the spine's search button must not swallow a press.
 *
 * nav-hub.js is on every page, and it lazy-loads search-overlay.js asynchronously. So
 * window.WHSearch is briefly absent on EVERY page load, and permanently absent if that request
 * fails - a cache miss, a bad deploy, a flaky plant connection.
 *
 * ★THE HANDLER HAD ONLY THE HAPPY BRANCH. `if (window.WHSearch) { open() }` and nothing else, so
 * a press with the script missing did nothing whatsoever. Measured with search-overlay.js answered
 * 404: the overlay never opened, NOTHING was said, and there were zero page errors - the exact
 * shape of a control that looks alive and is not, on the one element that appears on every page.
 *
 * THE ASSERTION, both directions:
 *   1. HEALTHY — pressing search opens the overlay, and does NOT cry unavailable.
 *   2. SCRIPT DEAD — the overlay does not open (honest), and the page SAYS so.
 * Direction 1 is what stops the fix from being "always claim it is broken", which would satisfy
 * direction 2 while destroying the feature.
 *
 * Driven at 390 because the hub is the phone's only navigation.
 *
 * Usage: node tools/prove_search_button_is_not_dead.mjs
 */
import { chromium } from 'playwright';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';

const v = {};
const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: 'block' });

  const drive = async (breakScript) => {
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
    if (breakScript) {
      await page.route('**/search-overlay.js', (r) => r.fulfill({ status: 404, body: '' }));
    }
    await page.goto(`${BASE}/logbook.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(6000);
    const out = await page.evaluate(async () => {
      const fab = document.getElementById('wh-hub-fab') || document.querySelector('[id*="hub-fab"]');
      if (fab) fab.click();
      await new Promise((r) => setTimeout(r, 600));
      const btn = document.getElementById('wh-hub-global-search');
      if (!btn) return { noButton: true };
      btn.click();
      await new Promise((r) => setTimeout(r, 2500));
      const ov = document.getElementById('wh-search-overlay');
      const t = document.body.innerText || '';
      return {
        overlayOpened: !!ov && getComputedStyle(ov).display !== 'none' && ov.offsetHeight > 0,
        saysUnavailable: /search is unavailable|search could not start/i.test(t),
      };
    });
    await page.close();
    return { ...out, errs: errs.length };
  };

  v.healthy = await drive(false);
  v.scriptDead = await drive(true);
  console.log(`  healthy     -> overlay=${v.healthy.overlayOpened} criesUnavailable=${v.healthy.saysUnavailable}`);
  console.log(`  script dead -> overlay=${v.scriptDead.overlayOpened} saysUnavailable=${v.scriptDead.saysUnavailable}`);
} catch (e) {
  v.error = String(e.message || e).slice(0, 170);
  console.log('probe error:', v.error);
} finally {
  await browser.close();
}

const h = v.healthy || {}, d = v.scriptDead || {};
const pass = !v.error && !h.noButton && !d.noButton
  && h.overlayOpened && !h.saysUnavailable
  && !d.overlayOpened && d.saysUnavailable
  && h.errs === 0 && d.errs === 0;

if (!pass && !v.error) {
  console.log('  A press that changes nothing teaches the worker the platform is broken and gives');
  console.log('  them nothing to do about it. Say why, on the one control every page carries.');
}
console.log((pass ? 'PASS' : 'FAIL') + ` — search button is not dead: ${JSON.stringify(v)}`);
process.exit(pass ? 0 : 1);
