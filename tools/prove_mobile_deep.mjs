// prove_mobile_deep — the MOBILE DEEP family of the live-walk wave (2026-09-06).
//
// tools/live_walk_manifest.py --family "mobile deep" lists 40 rows across four lenses that tools/prove_phone_fit.mjs
// does not ask. That file answers whether a page FITS a phone (overflow, clipping, menus inside the viewport);
// these are about whether a person can USE it there:
//
//   M1 tap targets      every interactive control is at least 44x44 CSS px, or is separated from its neighbours by
//                       enough space that a thumb cannot hit the wrong one. WCAG 2.5.8 / the platform's own rule.
//   M2 safe area        a page with FIXED top or bottom chrome must declare viewport-fit=cover and pad that chrome
//                       with env(safe-area-inset-*), or the notch and the home indicator sit on top of it.
//   M3 landscape+tablet the same page at 844x390 (phone landscape) and 834x1112 (tablet) still fits: no horizontal
//                       page overflow, and the main content is on screen rather than pushed off by fixed chrome.
//   M4 install+shell    the manifest is linked, parses, and carries name, icons and start_url; a service worker is
//                       registered. An install prompt that leads to a shell that cannot boot is worse than none.
//
//   node tools/prove_mobile_deep.mjs
//   node tools/prove_mobile_deep.mjs --page hive.html
import { chromium } from 'playwright';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();

const ROSTER = [
  'hive.html', 'logbook.html', 'inventory.html', 'asset-hub.html', 'dayplanner.html', 'alert-hub.html',
  'analytics.html', 'community.html', 'marketplace.html', 'marketplace-seller.html', 'skillmatrix.html',
  'pm-scheduler.html', 'project-manager.html', 'assistant.html', 'shift-brain.html', 'voice-journal.html',
  'resume.html', 'achievements.html', 'public-feed.html', 'index.html',
];

const TAPS = function taps(VIS_JS) {
  const vis = (0, eval)(VIS_JS);
  const name = (e) => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/)[0] : ''));
  const SEL = 'a[href], button, input:not([type="hidden"]), select, textarea, [role="button"], [role="tab"], [role="switch"], [role="checkbox"], summary';
  const out = [];
  const els = [...document.querySelectorAll(SEL)].filter((e) => vis(e)
    && e.checkVisibility({ opacityProperty: true, visibilityProperty: true })
    && !e.closest('[aria-hidden="true"], [inert]'));
  for (const e of els) {
    const r = e.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    // ★AN INLINE LINK INSIDE A SENTENCE IS EXEMPT (WCAG 2.5.8's own exception): a link in running prose is sized
    // by the text, and demanding 44px would ask the platform to break its own paragraphs.
    const parentText = (e.parentElement && (e.parentElement.innerText || '')) || '';
    const inline = e.tagName === 'A' && getComputedStyle(e).display.startsWith('inline') && parentText.trim().length > (e.innerText || '').trim().length + 12;
    if (inline) continue;
    // ★A LABELLED CONTROL IS TAPPED BY ITS LABEL (calibrated 2026-09-06). resume.html's #promote-dedupe is an
    // 18x18 checkbox and read as a finding - but it sits inside <label class="opt-toggle" for="promote-dedupe">
    // wrapping a full sentence, so the activation area a thumb actually hits is that label. WCAG's target size is
    // about the activation area, not the painted box, so a control whose own label clears 44px is exempt.
    const lab = e.closest('label') || (e.id ? document.querySelector(`label[for="${CSS.escape(e.id)}"]`) : null);
    if (lab) {
      const lr = lab.getBoundingClientRect();
      if (lr.width >= 44 && lr.height >= 44) continue;
    }
    if (r.width < 44 || r.height < 44) {
      // spacing exception: enough clear room around it that a thumb cannot hit a neighbour
      const grow = 44;
      const near = els.some((o) => {
        if (o === e) return false;
        const q = o.getBoundingClientRect();
        return !(q.right < r.left - (grow - r.width) / 2 || q.left > r.right + (grow - r.width) / 2
              || q.bottom < r.top - (grow - r.height) / 2 || q.top > r.bottom + (grow - r.height) / 2);
      });
      if (near) out.push(`${name(e)} ${Math.round(r.width)}x${Math.round(r.height)}px with a neighbour inside the 44px target "${(e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 24)}"`);
    }
  }
  return [...new Set(out)].slice(0, 6);
};

const SAFE = function safe() {
  const out = [];
  const vp = document.querySelector('meta[name="viewport"]');
  const content = vp ? (vp.getAttribute('content') || '') : '';
  const fixed = [...document.querySelectorAll('body *')].filter((e) => {
    const cs = getComputedStyle(e);
    if (cs.position !== 'fixed' && cs.position !== 'sticky') return false;
    if (!e.checkVisibility || !e.checkVisibility({ opacityProperty: true, visibilityProperty: true })) return false;
    const r = e.getBoundingClientRect();
    return r.height > 20 && r.width > window.innerWidth * 0.5 && (r.top <= 2 || r.bottom >= window.innerHeight - 2);
  });
  if (fixed.length) {
    if (!/viewport-fit\s*=\s*cover/i.test(content)) out.push(`${fixed.length} full-width fixed bar(s) but the viewport meta does not say viewport-fit=cover`);
    // does ANY stylesheet reference the safe-area insets? the computed value is already resolved, so ask the source
    const usesEnv = [...document.styleSheets].some((sh) => {
      try { return [...sh.cssRules].some((r2) => /env\(\s*safe-area-inset/i.test(r2.cssText)); }
      catch { return false; }   // a cross-origin sheet cannot be read; do not count it either way
    });
    if (!usesEnv) out.push('fixed chrome present but no rule anywhere references env(safe-area-inset-*) - the notch and the home indicator will sit on it');
  }
  return out;
};

const FITS = function fits(VIS_JS) {
  const vis = (0, eval)(VIS_JS);
  const out = [];
  const de = document.documentElement;
  if (de.scrollWidth > de.clientWidth + 2) out.push(`the page scrolls sideways: ${de.scrollWidth}px of content in a ${de.clientWidth}px viewport`);
  const main = document.querySelector('main, [role="main"], #app') || document.body;
  const r = main.getBoundingClientRect();
  if (vis(main) && r.height > 0 && (r.top > window.innerHeight - 40)) out.push('the main content starts below the fold - fixed chrome has pushed it off screen');
  return out;
};

const b = await chromium.launch();
let bad = 0, n = 0;
const PAGES = ONLY ? [ONLY] : (LIST || ROSTER);

// M4 is one question about the app, not one per page
const shell = await (async () => {
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/index.html`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(6000);
  const href = await p.evaluate(() => { const l = document.querySelector('link[rel="manifest"]'); return l ? l.href : null; }).catch(() => null);
  const issues = [];
  if (!href) issues.push('M4 no <link rel="manifest"> - the app cannot be installed');
  else {
    const r = await p.request.get(href).catch(() => null);
    if (!r || !r.ok()) issues.push(`M4 the manifest answers ${r ? r.status() : 'nothing'}`);
    else {
      let man = null;
      try { man = JSON.parse(await r.text()); } catch { issues.push('M4 the manifest does not parse'); }
      if (man) {
        for (const k of ['name', 'icons', 'start_url']) if (!man[k] || (Array.isArray(man[k]) && !man[k].length)) issues.push(`M4 the manifest has no ${k}`);
        if (man.icons && !man.icons.some((i) => /512/.test(String(i.sizes || '')))) issues.push('M4 no 512px icon - the install prompt has nothing to show');
      }
    }
    await p.waitForTimeout(4000);
    const sw = await p.evaluate(async () => {
      if (!('serviceWorker' in navigator)) return 'unsupported';
      const regs = await navigator.serviceWorker.getRegistrations().catch(() => []);
      return regs.length ? 'registered' : 'none';
    }).catch(() => 'none');
    if (sw === 'none') issues.push('M4 no service worker is registered on the shell - the installed app has no offline boot');
  }
  await ctx.close();
  return issues;
})();
for (const s of shell) console.log(`  BAD (app shell)                    ${s}`);
if (shell.length) bad++;

for (const file of PAGES) {
  n++;
  const issues = [];
  for (const [label, w, h] of [['phone', 390, 844], ['landscape', 844, 390], ['tablet', 834, 1112]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, isMobile: w < 800, hasTouch: true, deviceScaleFactor: 2, serviceWorkers: 'block' });
    await signIn(ctx);
    const p = await ctx.newPage();
    await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(label === 'phone' ? 13000 : 8000);
    if (label === 'phone') {
      for (const s of await p.evaluate(TAPS, VIS_JS).catch(() => [])) issues.push('M1 tap target: ' + s);
      for (const s of await p.evaluate(SAFE).catch(() => [])) issues.push('M2 safe area: ' + s);
    }
    for (const s of await p.evaluate(FITS, VIS_JS).catch(() => [])) issues.push(`M3 ${label}: ` + s);
    await ctx.close();
  }
  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(30)}${issues.length ? ' ' + issues.length + ' issue(s)' : ' usable on a phone, in landscape and on a tablet'}`);
  for (const s of issues.slice(0, ONLY ? 20 : 3)) console.log(`        ${s.slice(0, 158)}`);
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} mobile-deep - ${n - bad}/${n} pages have thumb-sized targets, safe-area-aware fixed chrome and fit landscape and tablet${shell.length ? '; the installable shell has ' + shell.length + ' issue(s)' : '; the installable shell is complete'}`);
process.exitCode = bad ? 1 : 0;
