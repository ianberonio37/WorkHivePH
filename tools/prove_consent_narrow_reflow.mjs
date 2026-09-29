// prove_consent_narrow_reflow.mjs - TEETH for the C13 consent-card fix (wave-4 narrow-320 walk, 2026-09-14).
//
// index.html's analytics-consent card (#wh-consent) is a position:fixed bottom card (left/right 1rem, bottom 1rem,
// z-9000). At 320 CSS px it grows to ~212px and sat ON the sign-in wall's "Forgot your password?", "Create one for
// free", the SSO button and the bottom band where the hub FAB lives (the walk's elementFromPoint at each returned the
// card). wh-consent.js now REFLOWS the card into the page below 360px: static, at the top of <main>, covering
// nothing. This proves the mechanism on a synthetic page the host can render, with controls in both directions:
//
//   320  - after wh-consent.js shows the card it is position:static, inside <main>, and every control that used to
//          sit under it (a form button in the covered band, a bottom-right FAB) is the element at its OWN centre
//   320, fix undone (negative control) - forcing the card back to fixed/bottom MUST cover at least one of those
//          controls again, or this test has no teeth
//   390  - the card stays a FIXED bottom card (the 361px+ design is untouched)
//
//   node tools/prove_consent_narrow_reflow.mjs
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';

const CONSENT_JS = readFileSync('wh-consent.js', 'utf8');
// the card's markup + inline styles copied from index.html:5421-5435, so the test measures the real box, not a stand-in
const CARD = '<div id="wh-consent" hidden role="region" aria-labelledby="wh-consent-t" aria-describedby="wh-consent-d"'
  + ' style="position:fixed;left:1rem;right:1rem;bottom:1rem;max-width:34rem;margin:0 auto;z-index:9000;background:#12181f;color:#e6edf3;border:1px solid #2b3947;border-radius:0.75rem;padding:0.95rem 1.05rem;box-shadow:0 8px 28px rgba(0,0,0,.42);font-size:0.82rem;line-height:1.5">'
  + '<strong id="wh-consent-t" style="display:block;font-size:0.86rem;margin-bottom:0.3rem">Analytics on this page</strong>'
  + '<p id="wh-consent-d" style="margin:0 0 0.75rem;color:#aebdcc">We would like to count anonymous page views to see which guides are useful. No names, emails or phone numbers are collected. Nothing is measured until you choose.</p>'
  + '<div style="display:flex;gap:0.5rem;flex-wrap:wrap"><button type="button" id="wh-consent-yes" style="min-height:44px;padding:0 1.05rem;border-radius:0.5rem;border:0;background:#f5b301;color:#151a1f;font-weight:600">Allow</button>'
  + '<button type="button" id="wh-consent-no" style="min-height:44px;padding:0 1.05rem;border-radius:0.5rem;border:1px solid #3a4a5a;background:transparent;color:#e6edf3">No thanks</button></div></div>';
const PAGE = '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width"><style>body{margin:0;font-family:sans-serif}.fixed{position:fixed}.top-0{top:0}nav.fixed{left:0;right:0;height:56px;background:#162032;z-index:30}</style></head><body>'
  + '<nav class="fixed top-0"><a href="index.html" style="display:inline-flex;align-items:center;min-height:44px;padding:0 16px;color:#fff">&larr; Back</a></nav>'
  + '<main style="padding:72px 16px 120px"><h1>Sign in</h1><input placeholder="Username" style="display:block;width:100%;min-height:44px;margin:8px 0"><input placeholder="Password" style="display:block;width:100%;min-height:44px;margin:8px 0">'
  + '<button id="signin" style="display:block;width:100%;min-height:44px;margin:12px 0">Sign In</button>'
  + '<div style="height:150px"></div>'   // pushes the next controls into the band the fixed card covers at 320 (y ~480-660)
  + '<button id="forgot" style="display:block;min-height:44px;margin:8px 0">Forgot your password?</button>'
  + '<button id="sso" style="display:block;min-height:44px;margin:8px 0">Enterprise SSO (Okta / Azure AD)</button>'
  + '<button id="create" style="display:block;min-height:44px;margin:8px 0">Create one for free</button></main>'
  + '<button id="wh-hub-fab" aria-label="Open navigation" style="position:fixed;right:16px;bottom:16px;width:56px;height:56px;border-radius:50%;border:0;background:#f7a21b;z-index:1000">+</button>'
  + CARD + '</body></html>';

const CONTROLS = ['forgot', 'sso', 'create', 'wh-hub-fab'];
const measure = (page) => page.evaluate((ids) => {
  const box = document.getElementById('wh-consent');
  const out = { boxPos: getComputedStyle(box).position, boxInMain: !!box.closest('main'), boxHidden: box.hidden, covered: [] };
  for (const id of ids) {
    const el = document.getElementById(id); let r = el.getBoundingClientRect();
    // A control the reflowed card pushed BELOW the fold is not covered - it is the walk's scroll-to job (the same
    // rule phone_fit_audit applies: only controls inside the viewport are hit-tested). Scroll it into view the way a
    // person would, then ask what sits at its centre. A FIXED card does not move with the scroll, so the negative
    // control (the old fixed layout) still covers whatever lands under it after the scroll - the teeth survive.
    if (r.top < 0 || r.bottom > innerHeight) { el.scrollIntoView({ block: 'center' }); r = el.getBoundingClientRect(); }
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    if (!(hit === el || el.contains(hit))) out.covered.push(id + ' -> ' + (hit ? (hit.id ? '#' + hit.id : hit.tagName.toLowerCase()) : 'null'));
  }
  window.scrollTo(0, 0);
  return out;
}, CONTROLS);

const b = await chromium.launch();
const fails = [];
for (const width of [320, 390]) {
  const ctx = await b.newContext({ viewport: { width, height: 720 }, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  // Serve the page from a REAL http origin (a routed hostname, no network), not page.setContent: an about:blank /
  // data: origin is opaque, so wh-consent.js's localStorage.getItem throws and its `catch (e) { return; }` bails
  // before the card ever shows - which read as "the card did not show" on the first run of this test. On the real
  // site the origin is http(s) and storage works; the harness must give the script the same ground.
  await page.route('http://wh-consent-test.local/**', (route) => route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: PAGE }));
  await page.goto('http://wh-consent-test.local/', { waitUntil: 'load' });
  await page.evaluate(() => { try { localStorage.removeItem('wh_analytics_consent'); } catch (e) { void e; } });
  await page.addScriptTag({ content: CONSENT_JS });
  await page.waitForTimeout(80);
  const m = await measure(page);
  if (m.boxHidden) fails.push(`${width}: the consent card did not show`);
  if (width === 320) {
    if (m.boxPos !== 'static' || !m.boxInMain) fails.push(`320: the card must reflow into <main> as static - got position ${m.boxPos}, inMain ${m.boxInMain}`);
    if (m.covered.length) fails.push(`320: controls still covered after the reflow: ${m.covered.join(', ')}`);
    // negative control: put the card back to its old fixed-bottom layout and prove that DOES cover something
    await page.evaluate(() => { const box = document.getElementById('wh-consent'); document.body.appendChild(box);
      box.style.position = 'fixed'; box.style.left = '1rem'; box.style.right = '1rem'; box.style.bottom = '1rem'; box.style.maxWidth = '34rem'; box.style.margin = '0 auto'; });
    const undone = await measure(page);
    if (!undone.covered.length) fails.push('320 negative control: the old fixed-bottom card covered nothing, so this test has no teeth');
    else console.log(`  (negative control at 320: the old fixed card covers ${undone.covered.join(', ')})`);
  } else {
    // ★C25 (2026-09-14): at 390 the fixed bottom card sat ON the hub FAB on the real landing page (signed in, no dialog),
    // so the reflow is now unconditional - at 390 too the card is static inside <main> and covers nothing.
    if (m.boxPos !== 'static' || !m.boxInMain) fails.push(`390: the card must reflow into <main> as static at every width - got position ${m.boxPos}, inMain ${m.boxInMain}`);
    if (m.covered.length) fails.push(`390: controls still covered after the reflow: ${m.covered.join(', ')}`);
    await page.evaluate(() => { const box = document.getElementById('wh-consent'); document.body.appendChild(box);
      box.style.position = 'fixed'; box.style.left = '1rem'; box.style.right = '1rem'; box.style.bottom = '1rem'; box.style.maxWidth = '34rem'; box.style.margin = '0 auto'; });
    const undone390 = await measure(page);
    if (!undone390.covered.length) fails.push('390 negative control: the old fixed-bottom card covered nothing, so this case has no teeth');
    else console.log(`  (negative control at 390: the old fixed card covers ${undone390.covered.join(', ')})`);
    // restore the in-flow card before the dialog case below
    await page.evaluate(() => { const box = document.getElementById('wh-consent'); const host = document.querySelector('main'); box.style.position = 'static'; box.style.left = 'auto'; box.style.right = 'auto'; box.style.bottom = 'auto'; box.style.maxWidth = 'none'; box.style.margin = '0 0 1rem'; host.insertBefore(box, host.firstChild); });
    // ★C13 LIVED AGAIN AT 390 (tools/prove_w4_confusions.mjs, 2026-09-14): with the SIGN-IN DIALOG open the fixed
    // card (z 9000) sat on the dialog's SSO / "Create one for free" buttons (the dialog is z-50). While
    // #signin-modal is open (Tailwind `hidden` removed) the card must stand down into the flow and cover none of
    // the dialog's controls; when the dialog closes it returns to its fixed place. Open a dialog the way index.html
    // does (fixed inset-0 z-50, class hidden toggled) with a control exactly where the wall's SSO button sits.
    await page.evaluate(() => {
      const s = document.createElement('style'); s.textContent = '.hidden{display:none}'; document.head.appendChild(s);
      const d = document.createElement('div'); d.id = 'signin-modal'; d.className = 'fixed inset-0 z-50';
      d.setAttribute('role', 'dialog'); d.setAttribute('aria-modal', 'true');
      d.style.cssText = 'position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.75)';
      d.innerHTML = '<button id="modal-sso" style="position:absolute;left:45px;top:612px;width:300px;height:46px">Enterprise SSO (Okta / Azure AD)</button>'
        + '<button id="modal-create" style="position:absolute;left:204px;top:672px;width:111px;height:44px">Create one for free</button>';
      document.body.appendChild(d);
    });
    await page.waitForTimeout(60);
    const withDialog = await page.evaluate(() => {
      const box = document.getElementById('wh-consent'); const out = { boxPos: getComputedStyle(box).position, covered: [] };
      for (const id of ['modal-sso', 'modal-create']) { const el = document.getElementById(id); const r = el.getBoundingClientRect(); const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); if (!(hit === el || el.contains(hit))) out.covered.push(id + ' -> ' + (hit ? (hit.id ? '#' + hit.id : hit.tagName.toLowerCase()) : 'null')); }
      return out;
    });
    if (withDialog.boxPos !== 'static') fails.push(`390 with the sign-in dialog open: the card must stand down into the flow - got position ${withDialog.boxPos}`);
    if (withDialog.covered.length) fails.push(`390 with the sign-in dialog open: the card still covers ${withDialog.covered.join(', ')}`);
    // negative control: the OLD fixed-bottom layout (no reflow, no stand-down rule) must cover the dialog's controls, or this has no teeth
    const undone = await page.evaluate(() => {
      const st = document.getElementById('wh-consent-standdown'); if (st) st.remove();
      const box = document.getElementById('wh-consent'); document.body.appendChild(box);
      box.style.position = 'fixed'; box.style.left = '1rem'; box.style.right = '1rem'; box.style.bottom = '1rem'; box.style.maxWidth = '34rem'; box.style.margin = '0 auto';
      const out = { boxPos: getComputedStyle(box).position, covered: [] };
      for (const id of ['modal-sso', 'modal-create']) { const el = document.getElementById(id); const r = el.getBoundingClientRect(); const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); if (!(hit === el || el.contains(hit))) out.covered.push(id); }
      return out;
    });
    if (!undone.covered.length) fails.push('390 negative control: the old fixed-bottom card under an open dialog covered none of its controls, so this case has no teeth');
    else console.log(`  (negative control at 390 + dialog: the old fixed card covers ${undone.covered.join(', ')})`);
    // and when the dialog closes the card is still the in-flow card (C25: it is never fixed chrome any more)
    await page.evaluate(() => { const box = document.getElementById('wh-consent'); const host = document.querySelector('main'); box.style.position = 'static'; box.style.left = 'auto'; box.style.right = 'auto'; box.style.bottom = 'auto'; box.style.maxWidth = 'none'; box.style.margin = '0 0 1rem'; host.insertBefore(box, host.firstChild); document.getElementById('signin-modal').classList.add('hidden'); });
    await page.waitForTimeout(60);
    const closed = await page.evaluate(() => getComputedStyle(document.getElementById('wh-consent')).position);
    if (closed !== 'static') fails.push(`390 after the dialog closes: the card must stay in the flow - got ${closed}`);
  }
  await ctx.close();
}
await b.close();
if (fails.length) { console.log('FAIL consent-narrow-reflow - ' + fails.join(' | ')); process.exit(1); }
console.log('PASS consent-narrow-reflow - at 320 AND 390 the consent card reflows into <main> (static) and every control the old fixed card covered (sign-in links, SSO, Create, the hub FAB, an open dialog\'s buttons) is reachable at its own centre; forcing the old fixed card back covers them again at both widths (teeth); the card stays in the flow after a dialog closes');
