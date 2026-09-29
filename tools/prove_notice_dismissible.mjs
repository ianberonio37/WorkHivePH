// prove_notice_dismissible.mjs - TEETH for the C15 fix (wave-4 narrow-320 walk, 2026-09-14).
//
// utils.js's shared transport notice (_whShowNotice: "Could not load ... try again" + a Retry/Reload/Sign-in
// button) is a position:fixed full-width bar at z-2147483000. On the tall 320 sign-in form its retry button sat ON
// the "Enterprise SSO" button (elementFromPoint at the SSO button's centre returned button.wh-notice-retry), so a
// person whose read failed lost a sign-in control until the read succeeded - and the notice offered no way to clear
// it. The fix gives every notice a 44px Dismiss (✕) that hides it and restores whatever it covered. This proves the
// mechanism on a synthetic page served from a real origin, with the REAL utils.js loaded:
//
//   shown    - _whShowNotice paints the notice with its retry button AND a .wh-notice-close control (>= 44px)
//   covered  - a control placed in the notice's band is NOT the element at its own centre while the notice is up
//              (the defect, reproduced - the test's negative control)
//   dismiss  - clicking ✕ hides the notice and that control is the element at its own centre again
//
//   node tools/prove_notice_dismissible.mjs
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';

const UTILS = readFileSync('utils.js', 'utf8');
const PAGE = '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width"><style>body{margin:0;font-family:sans-serif}</style></head><body>'
  + '<main style="padding:72px 16px 0"><h1>Sign in</h1>'
  + '<div style="height:430px"></div>'
  + '<button id="sso" style="display:block;width:100%;min-height:46px">Enterprise SSO (Okta / Azure AD)</button>'
  + '<div style="height:400px"></div></main></body></html>';

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 320, height: 720 }, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
await page.route('http://wh-notice-test.local/**', (route) => route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: PAGE }));
await page.goto('http://wh-notice-test.local/', { waitUntil: 'load' });
// utils.js initialises a lot on a real page; on this bare page its guarded init may log, but _whShowNotice is a
// top-level function declaration and is defined regardless of what later init does.
await page.addScriptTag({ content: UTILS }).catch(() => {});
const fails = [];

const hasFn = await page.evaluate(() => typeof window._whShowNotice === 'function');
if (!hasFn) { console.log('FAIL notice-dismissible - utils.js did not define _whShowNotice on the test page'); await b.close(); process.exit(1); }

// place the notice exactly over the SSO button's band: bottom = viewport height - (button bottom) + a little
const bottomPx = await page.evaluate(() => { const r = document.getElementById('sso').getBoundingClientRect(); return Math.max(8, Math.round(innerHeight - r.bottom)) + 'px'; });
await page.evaluate((bp) => window._whShowNotice('wh-test-notice', 'Could not load your data. Check your connection and try again.', bp), bottomPx);
await page.waitForTimeout(80);

const state = () => page.evaluate(() => {
  const n = document.getElementById('wh-test-notice'); const sso = document.getElementById('sso');
  const r = sso.getBoundingClientRect(); const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  const close = n ? n.querySelector('.wh-notice-close') : null; const cr = close ? close.getBoundingClientRect() : null;
  const shown = !!n && n.style.display !== 'none' && n.getBoundingClientRect().height > 0;
  return { shown, hasRetry: !!(n && n.querySelector('.wh-notice-retry')), hasClose: !!close,
    closeBig: !!cr && cr.width >= 44 && cr.height >= 44, ssoReachable: !!hit && (hit === sso || sso.contains(hit)),
    hitName: hit ? (hit.id ? '#' + hit.id : hit.className || hit.tagName) : null };
});

const up = await state();
if (!up.shown || !up.hasRetry) fails.push(`the notice did not paint with its retry control (shown ${up.shown}, retry ${up.hasRetry})`);
if (!up.hasClose) fails.push('the notice has NO dismiss control (.wh-notice-close) - the C15 fix is missing');
else if (!up.closeBig) fails.push('the dismiss control is smaller than 44x44');
if (up.ssoReachable) fails.push('negative control: the notice placed over the SSO button did not cover it, so this test has no teeth');
else console.log(`  (negative control: while the notice is up the SSO button's centre hits ${up.hitName})`);

if (up.hasClose) {
  await page.click('#wh-test-notice .wh-notice-close', { timeout: 4000 }).catch((e) => fails.push('the dismiss control could not be clicked: ' + String(e.message).split('\n')[0]));
  await page.waitForTimeout(80);
  const after = await state();
  if (after.shown) fails.push('after Dismiss the notice is still shown');
  if (!after.ssoReachable) fails.push(`after Dismiss the SSO button is still covered (hit ${after.hitName})`);
}

await b.close();
if (fails.length) { console.log('FAIL notice-dismissible - ' + fails.join(' | ')); process.exit(1); }
console.log('PASS notice-dismissible - the transport notice paints with Retry AND a 44px Dismiss; placed over a control it covers it (teeth); Dismiss hides it and the control is reachable at its own centre again');
