/**
 * T44: what happens to a live session when a NEW service worker ships under it? (2026-08-28)
 *
 * The deploy question nobody had measured: an installed PWA is running v_N when v_N+1 lands. Does
 * the new worker sit in `waiting` until every tab closes (stranding people on the old build for
 * days — the April stale-nav incident's shape)? Does the old cache vanish out from under a page
 * that is still using it? Is anyone told?
 *
 * MEASURED, by replacing sw.js on disk while a logbook page sat open and calling registration
 * .update():
 *   before : caches ["workhive-shell-v241"], worker controlling the page
 *   after  : installing false · waiting FALSE · active true · caches ["workhive-shell-vT44TEST"]
 *   nudge  : none — no "new version available" text anywhere on the page
 *
 * WHAT THAT MEANS, read against the worker's own handlers rather than guessed: install does
 * `caches.open(NEW).then(c => c.addAll(SHELL_FILES))` inside waitUntil, so the NEW cache is fully
 * populated before install resolves; activate then deletes every key that is not the new one; and
 * skipWaiting() + clients.claim() hand the live page to the new worker immediately. So the strategy
 * is "newest wins at once", there is never a moment without a usable shell, and the absence of an
 * update nudge is consistent rather than missing — the nudge exists for designs that leave the new
 * worker WAITING, which this one deliberately does not.
 *
 * The residual mixed-version window is bounded and worth stating: the page already rendered keeps
 * its old HTML/JS until the next navigation while the cache holds the new files. Because this
 * shell precaches whole PAGES rather than hashed chunks, an old page cannot fetch a mismatched
 * fragment — the classic chunk-mismatch failure does not apply here.
 *
 * ★NOT A BOARD GATE: it REWRITES sw.js mid-run (restoring it in a finally, and asserting the
 * restore). That is fine to drive deliberately before a deploy; it is not something to do on every
 * board pass. Run it when the worker's lifecycle changes.
 *
 * ★AND IT NEEDS serviceWorkers ENABLED — every other probe here blocks them, and this is the one
 * whose entire subject is the worker.
 *
 * USAGE:  node tools/prove_sw_two_version_transition.mjs
 */
import { chromium } from 'playwright';
import fs from 'node:fs';

const BASE = 'http://127.0.0.1:5000/workhive';
const SW = 'sw.js';
const original = fs.readFileSync(SW, 'utf-8');
const vBefore = (original.match(/CACHE_NAME\s*=\s*['"]([^'"]+)/) || [])[1];

const browser = await chromium.launch();
// ★serviceWorkers must be ENABLED here — every other probe blocks them, and this is the one test
// whose entire subject is the worker.
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

try {
  await page.goto(`${BASE}/logbook.html`, { waitUntil: 'domcontentloaded' });
  // wait for the FIRST worker to control the page
  const first = await page.evaluate(async () => {
    const r = await navigator.serviceWorker.ready.catch(() => null);
    if (!r) return null;
    for (let i = 0; i < 30 && !navigator.serviceWorker.controller; i++) await new Promise(s => setTimeout(s, 300));
    return { scope: r.scope, hasController: !!navigator.serviceWorker.controller,
             caches: await caches.keys() };
  });
  console.log('v_N active     :', JSON.stringify(first));
  console.log('CACHE_NAME on disk before:', vBefore);

  // ── ship v_N+1 UNDER the live session ────────────────────────────────────
  const bumped = original.replace(vBefore, 'workhive-shell-vT44TEST');
  fs.writeFileSync(SW, bumped);
  console.log('shipped v_N+1  : workhive-shell-vT44TEST (file replaced while the page is open)');

  const after = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.getRegistration();
    if (!reg) return { err: 'no registration' };
    await reg.update();                       // what a reload/periodic check would do
    await new Promise(s => setTimeout(s, 3000));
    return {
      installing: !!reg.installing, waiting: !!reg.waiting, active: !!reg.active,
      // is the OLD worker still the one serving this page?
      controllerIsOld: !!navigator.serviceWorker.controller,
      caches: await caches.keys(),
    };
  });
  console.log('after update() :', JSON.stringify(after));

  // does anything TELL the person a new version is ready?
  const nudge = await page.evaluate(() => {
    const t = (document.body.innerText || '').toLowerCase();
    return { mentionsUpdate: /new version|update available|refresh to update|reload to update/.test(t) };
  });
  console.log('update nudge   :', JSON.stringify(nudge));
} catch (e) {
  console.log('probe error:', String(e.message || e).slice(0, 160));
} finally {
  fs.writeFileSync(SW, original);
  const vAfter = (fs.readFileSync(SW, 'utf-8').match(/CACHE_NAME\s*=\s*['"]([^'"]+)/) || [])[1];
  console.log('sw.js restored :', vAfter, vAfter === vBefore ? '(matches original)' : '(MISMATCH)');
  await browser.close();
}
