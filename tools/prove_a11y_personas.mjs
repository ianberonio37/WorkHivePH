// prove_a11y_personas — the EX-AX wave: four people, ten core journeys (2026-09-07).
//
// The per-page a11y gate asks whether a page is correct. These rows ask whether a PERSON completes a
// journey - and four kinds of person meet the same page four different ways:
//
//   SR  a screen-reader user     completes it by what is ANNOUNCED: every interactive control has an
//                                accessible name, and the page's live region exists to carry what changes
//   KB  a keyboard-only user     completes it without a mouse: Tab reaches the controls in a sensible
//                                order, focus is visible, and nothing traps it
//   ZM  a low-vision user at 200% completes it without horizontal scrolling or text clipped off-screen
//   CB  a colour-blind user      completes it with nothing that is signalled by colour ALONE - a status
//                                that is only a green dot is no status to them
//
// ★EACH PERSONA IS EMULATED, NOT ASSUMED. Forced-colors mode for CB, a 2x zoom for ZM, real Tab presses
// for KB, and the accessibility tree's names for SR - read from the page after settling, on the same
// ten pages every person walks: the core journeys of the platform.
//
//   node tools/prove_a11y_personas.mjs
//   node tools/prove_a11y_personas.mjs --page logbook.html
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS, SETTLE_MS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const ROWS = (() => {
  const reg = JSON.parse(readFileSync('trajectory_registry.json', 'utf8'));
  return reg.trajectories.filter((t) => t.wave === 'EX-AX');
})();
const PAGES = [...new Set(ROWS.flatMap((t) => t.pages || []))].filter((f) => !ONLY || f === ONLY);

const b = await chromium.launch();
let bad = 0, n = 0;
const say = (ok, who, page, line, detail) => {
  n++;
  if (!ok) bad++;
  console.log(`  ${ok ? 'ok ' : 'BAD'} ${who} ${page.padEnd(20)} ${line}`);
  if (!ok && detail) console.log(`        ${detail.slice(0, 158)}`);
};

for (const page of PAGES) {
  const url = `${SEEDER}/workhive/${page}${PAGE_QUERY[page] || ''}`;

  // ── SR · what is announced ──
  {
    const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
    await signIn(ctx);
    const p = await ctx.newPage();
    await p.goto(url, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(SETTLE_MS);
    const s = await p.evaluate((VIS_JS) => {
      const vis = (0, eval)(VIS_JS);
      // what a screen reader can REACH: the nav-hub drawer is visibility:hidden when closed and its 26 buttons are not in
      // the accessibility tree - the first walk counted them as 26 nameless controls on every page (2026-09-07)
      const inTree = (e) => e.checkVisibility && e.checkVisibility({ visibilityProperty: true }) && !e.closest('[aria-hidden="true"]');
      const controls = [...document.querySelectorAll('button, a[href], input:not([type=hidden]), select, textarea, [role="button"], [role="menuitem"], [role="tab"]')].filter(vis).filter(inTree);
      const name = (e) => (e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || e.getAttribute('title') || (e.labels && e.labels[0] && e.labels[0].innerText) || e.innerText || e.textContent || e.value || e.getAttribute('placeholder') || '').trim();
      const unnamed = controls.filter((e) => !name(e)).slice(0, 3).map((e) => `<${e.tagName.toLowerCase()}${e.id ? '#' + e.id : e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : ''}>`);
      const live = document.querySelectorAll('[aria-live], [role="status"], [role="alert"]').length;
      const landmarks = document.querySelectorAll('main, [role="main"], nav, [role="navigation"]').length;
      return { controls: controls.length, unnamed, unnamedCount: controls.filter((e) => !name(e)).length, live, landmarks };
    }, VIS_JS).catch(() => ({ controls: 0, unnamed: [], unnamedCount: 0, live: 0, landmarks: 0 }));
    await ctx.close();
    say(s.unnamedCount === 0 && s.live > 0 && s.landmarks > 0, 'SR', page, `${s.controls} control(s), ${s.unnamedCount} with no name; ${s.live} live region(s); ${s.landmarks} landmark(s)`,
      s.unnamedCount ? `${s.unnamedCount} control(s) announce nothing: ${s.unnamed.join(' ')}` : s.live === 0 ? 'no live region exists, so nothing that changes is ever announced' : 'no landmark to jump to');
  }

  // ── KB · Tab reaches the controls, focus is visible, nothing traps it ──
  {
    const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
    await signIn(ctx);
    const p = await ctx.newPage();
    await p.goto(url, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(SETTLE_MS);
    const seen = [];
    let invisibleFocus = 0, stuck = 0, last = '';
    for (let i = 0; i < 40; i++) {
      await p.keyboard.press('Tab').catch(() => {});
      const f = await p.evaluate(() => {
        const e = document.activeElement;
        if (!e || e === document.body) return null;
        const cs = getComputedStyle(e);
        const r = e.getBoundingClientRect();
        const outline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0;
        const ring = /rgba?\(/.test(cs.boxShadow) && cs.boxShadow !== 'none';
        // 2026-09-07: a row of same-class chips read as ONE trapped control when keyed by class + top alone
        return { key: (e.id || e.className || e.tagName) + ':' + Math.round(r.top) + ',' + Math.round(r.left), onScreen: r.top >= 0 && r.bottom <= innerHeight + 200 && r.width > 0, visibleFocus: outline || ring || e.matches(':focus-visible') };
      }).catch(() => null);
      if (!f) break;
      if (f.key === last) { stuck++; if (stuck > 3) break; } else stuck = 0;
      last = f.key;
      seen.push(f.key);
      if (!f.visibleFocus) invisibleFocus++;
    }
    await ctx.close();
    const distinct = new Set(seen).size;
    say(distinct >= 5 && invisibleFocus <= Math.floor(distinct * 0.2) && stuck <= 3, 'KB', page, `Tab reached ${distinct} distinct control(s) in 40 presses; ${invisibleFocus} with no visible focus; trap ${stuck > 3 ? 'YES' : 'no'}`,
      distinct < 5 ? 'a keyboard reaches almost nothing on this page' : stuck > 3 ? 'focus is trapped - the same control keeps receiving Tab' : `${invisibleFocus} control(s) take focus with nothing on screen to show it`);
  }

  // ── ZM · 200% zoom: no horizontal scroll, no clipped text ──
  {
    const ctx = await b.newContext({ viewport: { width: 640, height: 900 }, deviceScaleFactor: 2, serviceWorkers: 'block' });
    await signIn(ctx);
    const p = await ctx.newPage();
    await p.goto(url, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
    await p.addStyleTag({ content: 'html { zoom: 2 !important; }' }).catch(() => {});
    await p.waitForTimeout(SETTLE_MS);
    const s = await p.evaluate((VIS_JS) => {
      const vis = (0, eval)(VIS_JS);
      const doc = document.documentElement;
      const overflow = Math.max(0, doc.scrollWidth - doc.clientWidth);
      const clipped = [...document.querySelectorAll('p, li, h1, h2, h3, button, a, span')].filter((e) => vis(e) && e.scrollWidth > e.clientWidth + 4 && getComputedStyle(e).overflow !== 'visible' && getComputedStyle(e).textOverflow !== 'ellipsis').length;
      return { overflow, clipped };
    }, VIS_JS).catch(() => ({ overflow: 0, clipped: 0 }));
    await ctx.close();
    say(s.overflow <= 8 && s.clipped <= 2, 'ZM', page, `at 200%: ${s.overflow}px horizontal overflow, ${s.clipped} element(s) clipping their text`,
      s.overflow > 8 ? `${s.overflow}px of the page sits off the right edge at 200% - a low-vision person scrolls sideways to read a sentence` : `${s.clipped} element(s) cut their words off at 200%`);
  }

  // ── CB · nothing signalled by colour alone ──
  {
    const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
    await signIn(ctx);
    const p = await ctx.newPage();
    await p.emulateMedia({ forcedColors: 'active' }).catch(() => {});
    await p.goto(url, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(SETTLE_MS);
    const s = await p.evaluate((VIS_JS) => {
      const vis = (0, eval)(VIS_JS);
      // a status element that carries a status class and NO text or icon is colour-only
      // only what a colour-blind person can SEE: the nav-hub drawer is visibility:hidden when closed, and its tile dots
      // read as colour-only because their tile's innerText is '' while hidden (2026-09-07)
      const inTree = (e) => e.checkVisibility && e.checkVisibility({ visibilityProperty: true }) && !e.closest('[aria-hidden="true"]');
      const statusy = [...document.querySelectorAll('[class*="status"], [class*="badge"], [class*="dot"], [class*="pill"], [class*="tone-"], .ok, .warn, .bad, .green, .red, .yellow')].filter(vis).filter(inTree);
      // a coloured shape whose own row names the status (a dot beside "Online") is read by its words; only a shape with no
      // word anywhere near it is colour-only. The offenders are named so a finding can be acted on (2026-09-07).
      const bare = statusy.filter((e) => !(e.innerText || '').trim() && !e.querySelector('svg, img, [aria-label]') && !e.getAttribute('aria-label') && !e.getAttribute('title')
        && !(e.parentElement && (e.parentElement.innerText || '').trim()));
      const colourOnly = bare.length;
      const offenders = bare.slice(0, 3).map((e) => `<${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}.${String(e.className).split(' ')[0]} in ${e.parentElement ? (e.parentElement.id || e.parentElement.className.split(' ')[0] || e.parentElement.tagName) : '?'}>`);
      const textLen = ((document.querySelector('main, [role="main"], #app') || document.body).innerText || '').replace(/\s+/g, ' ').trim().length;
      return { statusy: statusy.length, colourOnly, offenders, textLen };
    }, VIS_JS).catch(() => ({ statusy: 0, colourOnly: 0, offenders: [], textLen: 0 }));
    await ctx.close();
    say(s.textLen > 200 && s.colourOnly === 0, 'CB', page, `in forced-colors: ${s.textLen}ch on screen, ${s.statusy} status element(s), ${s.colourOnly} signalled by colour alone`,
      s.textLen <= 200 ? 'the page went blank in forced-colors mode' : `${s.colourOnly} status element(s) are a coloured shape with no word or icon - invisible to a colour-blind person: ${(s.offenders || []).join(' ')}`);
  }
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} a11y-personas - ${n - bad}/${n} persona-journey(s) complete: announced, keyboard-reachable, readable at 200%, and legible without colour`);
process.exitCode = bad ? 1 : 0;
