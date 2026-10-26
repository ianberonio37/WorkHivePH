// prove_text_grows.mjs - OWN "the text grows and the colours are taken away" (2026-10-27).
//
// Two asks per page, each at phone-390 and desktop-1280. Each is DIFFERENTIAL, with prove_zoom200's discipline: ONE page,
// ONE load, measured, then the condition is applied to that same page and it is measured again. A defect counts only if
// the second reading has it and the first does not, so a table that always scrolls is not blamed on large text.
//
//   GROW    WCAG 1.4.4 (text at 200%) together with 1.4.12 (line-height 1.5, paragraph spacing 2em, letter-spacing
//           0.12em, word-spacing 0.16em - applied as a constructed stylesheet, which no page CSP can refuse; the rail
//           below proves it took).
//             desktop-1280  browser zoom, as prove_zoom200 established it: the same page resized to a 640x400 CSS
//                           viewport (zoom halves the CSS pixels the layout gets; it does not scale them)
//             phone-390     a phone's large-text setting grows the TEXT and leaves the layout width alone: each
//                           element's computed font-size doubled in place, viewport unchanged
//           Defects: the document scrolls sideways; text is clipped across, or DOWNWARD (the 1.4.12 shape: a fixed-height
//           box); a control offered before is offered nowhere after (zoom200's accessible-name set, with the page's own
//           disclosures pressed first).
//   FORCED  forced-colors: active (High Contrast on Windows). The browser repaints with a system palette and REMOVES
//           backgrounds, gradients and box-shadows. Defects: a control that had ink before (pixels in its box that
//           differ from its own background) and has none now - still in the DOM, still focusable, invisible; and a
//           control whose keyboard focus showed before and shows nothing now (a box-shadow ring is erased).
//           Both are read from SCREENSHOTS, never computed styles: the forced palette is applied at paint.
//
//   node tools/prove_text_grows.mjs [--page achievements.html] [--ask grow|forced]  -> text_grows_report.json
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn, PAGE_QUERY } from './prover_harness.mjs';
import { measure, recoverDisclosures } from './lib/zoom_measure.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const OUT = path.join(ROOT, 'text_grows_report.json');
const args = process.argv.slice(2);
const opt = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; };
const ONE = opt('--page');
const ASKS = opt('--ask') ? [opt('--ask')] : ['grow', 'forced'];

const reg = JSON.parse(readFileSync(path.join(ROOT, 'trajectory_registry.json'), 'utf8'));
const PAGES = ONE ? ONE.split(',') : [...new Set((reg.trajectories || []).filter((r) => r.wave === 'OWN' && r.own
  && r.own.lens === 'text grows / colours taken away').map((r) => r.own.page))].sort();
// a top-level .html is an app page and is walked signed in; a directory page is public and is walked as a visitor
const isApp = (p) => !p.includes('/');
const QUERY = { ...PAGE_QUERY, 'project-report.html': '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc' };
const urlOf = (p) => isApp(p) ? `${ORIGIN}/workhive/${p}${QUERY[p] || ''}` : ORIGIN + '/' + p.replace(/index\.html$/, '');
const VIEWPORTS = { 'phone-390': { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
                    'desktop-1280': { viewport: { width: 1280, height: 800 } } };

const SPACING = '* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; }'
  + ' p { margin-bottom: 2em !important; }';
// in-page: the 1.4.12 overrides as a CONSTRUCTED sheet (CSP governs <style> and style attributes, not adoptedStyleSheets)
const applySpacing = (css) => {
  const s = new CSSStyleSheet(); s.replaceSync(css);
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, s];
  const p = document.querySelector('p') || document.body;
  return parseFloat(getComputedStyle(p).letterSpacing) || 0;       // the rail: 0 means the overrides did not apply
};
// in-page: the phone's large-text setting - every element's font-size read FIRST, then each doubled
const doubleText = () => {
  const els = [...document.querySelectorAll('body, body *')].filter((e) => !(e instanceof SVGElement));
  const fs = els.map((e) => parseFloat(getComputedStyle(e).fontSize) || 0);
  els.forEach((e, i) => { if (fs[i] > 0) e.style.setProperty('font-size', (fs[i] * 2) + 'px', 'important'); });
  const p = document.querySelector('p') || document.body;
  return { n: els.length, pFont: parseFloat(getComputedStyle(p).fontSize) || 0 };
};

const CTRL = 'button, a[href], input:not([type=hidden]), select, textarea, [role="button"], [role="tab"], [onclick]';
// in-page: the controls fully inside the viewport that are really on top at their own centre, not yet measured
const boxesInView = ([CTRL, done]) => {
  const seen = new Set(done); const out = [];
  const nameOf = (el) => (el.getAttribute('aria-label') || el.title || (el.innerText || '').trim() || el.value
    || (el.querySelector && el.querySelector('img[alt]') ? el.querySelector('img[alt]').alt : '') || el.tagName).replace(/\s+/g, ' ').trim().slice(0, 50);
  [...document.querySelectorAll(CTRL)].forEach((el, i) => {
    if (seen.has(i)) return;
    if (!(el.checkVisibility ? el.checkVisibility({ visibilityProperty: true, opacityProperty: true }) : el.offsetParent)) return;
    const r = el.getBoundingClientRect();
    if (r.width < 6 || r.height < 6 || r.top < 0 || r.left < 0 || r.bottom > innerHeight || r.right > innerWidth) return;
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    if (!hit || !(el === hit || el.contains(hit))) return;
    out.push({ i, name: nameOf(el), x: r.left, y: r.top, w: r.width, h: r.height });
  });
  return out;
};
// helper page: decode a PNG and count, inside each box, the pixels far from the box's own dominant colour
const inkIn = async ({ b64, boxes }) => {
  const bmp = await createImageBitmap(await (await fetch('data:image/png;base64,' + b64)).blob());
  const c = new OffscreenCanvas(bmp.width, bmp.height); const g = c.getContext('2d'); g.drawImage(bmp, 0, 0);
  const out = {};
  for (const b of boxes) {
    const x = Math.ceil(b.x), y = Math.ceil(b.y), w = Math.floor(b.x + b.w) - x, h = Math.floor(b.y + b.h) - y;
    if (w < 3 || h < 3) continue;
    const d = g.getImageData(x, y, w, h).data;
    const counts = new Map();
    for (let p = 0; p < d.length; p += 4) { const k = ((d[p] >> 4) << 8) | ((d[p + 1] >> 4) << 4) | (d[p + 2] >> 4); counts.set(k, (counts.get(k) || 0) + 1); }
    let dom = 0, best = -1; for (const [k, v] of counts) if (v > best) { best = v; dom = k; }
    const dr = ((dom >> 8) & 15) * 16 + 8, dg = ((dom >> 4) & 15) * 16 + 8, db = (dom & 15) * 16 + 8;
    let ink = 0;
    for (let p = 0; p < d.length; p += 4) if (Math.max(Math.abs(d[p] - dr), Math.abs(d[p + 1] - dg), Math.abs(d[p + 2] - db)) > 48) ink++;
    out[b.i] = { name: b.name, ink, px: w * h };
  }
  return out;
};
const diffPx = async ({ a, b }) => {
  const dec = async (s) => { const bm = await createImageBitmap(await (await fetch('data:image/png;base64,' + s)).blob());
    const c = new OffscreenCanvas(bm.width, bm.height); const g = c.getContext('2d'); g.drawImage(bm, 0, 0); return g.getImageData(0, 0, bm.width, bm.height); };
  const A = await dec(a), B = await dec(b);
  if (A.width !== B.width || A.height !== B.height) return -1;
  let n = 0;
  for (let p = 0; p < A.data.length; p += 4) if (Math.max(Math.abs(A.data[p] - B.data[p]), Math.abs(A.data[p + 1] - B.data[p + 1]), Math.abs(A.data[p + 2] - B.data[p + 2])) > 40) n++;
  return n;
};
const INK_MIN = (px) => Math.max(6, Math.round(px * 0.003));

async function scrollTo(pg, y) { await pg.evaluate((y) => window.scrollTo({ top: y, left: 0, behavior: 'instant' }), y); }

// every control's ink, read screen by screen (each control once, at the first screen that shows all of it on top)
async function inkOf(pg, helper) {
  const vh = pg.viewportSize().height;
  const H = await pg.evaluate(() => Math.min(document.documentElement.scrollHeight, 40000));
  const done = []; const out = {};
  for (let y = 0; y < H; y += Math.round(vh * 0.85)) {
    await scrollTo(pg, y); await pg.waitForTimeout(150);
    const boxes = await pg.evaluate(boxesInView, [CTRL, done]).catch(() => []);
    if (!boxes.length) continue;
    const shot = await pg.screenshot({ type: 'png', scale: 'css' });
    Object.assign(out, await helper.evaluate(inkIn, { b64: shot.toString('base64'), boxes }));
    boxes.forEach((b) => done.push(b.i));
  }
  await scrollTo(pg, 0);
  return out;
}

// keyboard focus, ten Tabs from the top: the control's neighbourhood focused vs the same control blurred
async function focusRings(pg, helper) {
  await scrollTo(pg, 0);
  await pg.evaluate(() => { const s = document.createElement('span'); s.id = '__whTabStart'; s.tabIndex = -1;
    s.style.cssText = 'position:absolute;top:0;left:0;width:1px;height:1px;overflow:hidden'; document.body.prepend(s); s.focus(); });
  const out = []; const vp = pg.viewportSize();
  for (let k = 0; k < 10; k++) {
    await pg.keyboard.press('Tab'); await pg.waitForTimeout(260);
    const f = await pg.evaluate(() => {
      const a = document.activeElement;
      if (!a || a === document.body || a.id === '__whTabStart') return null;
      const r = a.getBoundingClientRect();
      return { name: (a.getAttribute('aria-label') || a.title || (a.innerText || '').trim() || a.value || a.tagName).replace(/\s+/g, ' ').slice(0, 50),
        tag: a.tagName, x: r.left, y: r.top, w: r.width, h: r.height };
    });
    if (!f) break;
    const x = Math.max(0, Math.floor(f.x - 6)), y = Math.max(0, Math.floor(f.y - 6));
    const w = Math.min(vp.width - x, Math.ceil(f.w + 12)), h = Math.min(vp.height - y, Math.ceil(f.h + 12));
    if (w < 4 || h < 4) { out.push({ ...f, k, shown: null }); continue; }
    const clip = { x, y, width: w, height: h };
    const A = await pg.screenshot({ type: 'png', scale: 'css', clip });
    await pg.evaluate(() => { window.__whLastFocus = document.activeElement; if (document.activeElement) document.activeElement.blur(); });
    await pg.waitForTimeout(260);
    const B = await pg.screenshot({ type: 'png', scale: 'css', clip });
    const n = await helper.evaluate(diffPx, { a: A.toString('base64'), b: B.toString('base64') });
    out.push({ k, tag: f.tag, name: f.name, diff: n, shown: n >= 6 });
    // carry on from the same control: the next Tab must leave from here, not from the top
    await pg.evaluate(() => { try { window.__whLastFocus.focus({ preventScroll: true }); } catch (_) {} });
    await pg.waitForTimeout(80);
  }
  await pg.evaluate(() => { const s = document.getElementById('__whTabStart'); if (s) s.remove(); if (document.activeElement) document.activeElement.blur(); });
  return out;
}

// in-page: WHAT pushes the document sideways - the deepest boxes past the right edge that no scroll container of their
// own holds (a table inside an overflow-x:auto region overflows its region, not the page, and is not a culprit)
const culprits = () => {
  const W = document.documentElement.clientWidth;
  const held = (e) => { for (let a = e.parentElement; a && a !== document.body; a = a.parentElement) {
    const ox = getComputedStyle(a).overflowX; if (ox !== 'visible' && ox !== 'clip' && a.getBoundingClientRect().right <= W + 1) return true; } return false; };
  const over = [...document.querySelectorAll('body *')].filter((e) => { const r = e.getBoundingClientRect();
    return r.width > 0 && r.right > W + 1 && getComputedStyle(e).position !== 'fixed' && !held(e); });
  return over.filter((e) => !over.some((o) => o !== e && e.contains(o))).slice(0, 5).map((e) => {
    const r = e.getBoundingClientRect();
    return `<${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}${typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : ''}> `
      + `right ${Math.round(r.right)} "${(e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 30)}"`;
  });
};

const keyed = (m) => Object.fromEntries(Object.entries(m).map(([i, v]) => [i + '|' + v.name, v]));

async function open(browser, page, vpName) {
  const ctx = await browser.newContext({ ...VIEWPORTS[vpName], serviceWorkers: 'block', timezoneId: 'Asia/Manila' });
  if (isApp(page)) await assertSignedIn(signIn(ctx));
  const pg = await ctx.newPage();
  await pg.goto(urlOf(page), { waitUntil: 'domcontentloaded', timeout: 30000 });
  await pg.waitForTimeout(isApp(page) ? 6000 : 2200);
  return { ctx, pg };
}

function layoutFindings(a, b) {
  const reflow = b.docScrollX > 4 && a.docScrollX <= 4;
  const clipped = Object.entries(b.clipped).filter(([k]) => !(k in a.clipped)).map(([k, v]) => ({ el: k, over: v.over, text: v.text }));
  const clippedY = Object.entries(b.clippedY || {}).filter(([k]) => !(k in (a.clippedY || {}))).map(([k, v]) => ({ el: k, over: v.over, text: v.text }));
  return { reflow, docScrollX: [a.docScrollX, b.docScrollX], clipped: clipped.slice(0, 6), nClipped: clipped.length,
    clippedY: clippedY.slice(0, 6), nClippedY: clippedY.length };
}

async function grow(browser, page, vpName) {
  const { ctx, pg } = await open(browser, page, vpName);
  try {
    const a = await pg.evaluate(measure);
    if (a.nControls === 0 && a.textLen < 40) return { vp: vpName, ok: null, why: 'nothing rendered - UNGRADED' };
    const spacing = await pg.evaluate(applySpacing, SPACING);
    let grown;
    if (vpName === 'phone-390') grown = await pg.evaluate(doubleText);
    else { await pg.setViewportSize({ width: 640, height: 400 }); grown = { viewport: '640x400' }; }
    await pg.waitForTimeout(2500);
    const b = await pg.evaluate(measure);
    let lost = Object.keys(a.names).filter((n) => !b.names[n]);
    let pressed = 0;
    if (lost.length) {
      pressed = await pg.evaluate(recoverDisclosures).catch(() => 0);
      if (pressed) { await pg.waitForTimeout(1200); const c = await pg.evaluate(measure); lost = lost.filter((n) => !c.names[n]); }
    }
    const L = layoutFindings(a, b);
    if (L.reflow) L.culprits = await pg.evaluate(culprits).catch(() => []);
    if (!(spacing > 0)) return { vp: vpName, ok: null, why: 'the 1.4.12 overrides did not apply - UNGRADED', spacing };
    const ok = !L.reflow && !L.nClipped && !L.nClippedY && !lost.length;
    return { vp: vpName, ok, controls: a.nControls, names: Object.keys(a.names).length, spacing, grown, ...L,
      lost: lost.slice(0, 6), nLost: lost.length, disclosuresPressed: pressed };
  } catch (e) { return { vp: vpName, ok: null, why: 'ERROR ' + String(e.message || e).slice(0, 160) }; }
  finally { await ctx.close().catch(() => {}); }
}

async function forced(browser, helper, page, vpName) {
  const { ctx, pg } = await open(browser, page, vpName);
  try {
    // a warm pass first: reveal-on-scroll content must be revealed before the baseline reads its ink
    const H = await pg.evaluate(() => Math.min(document.documentElement.scrollHeight, 40000));
    for (let y = 0; y < H; y += 600) { await scrollTo(pg, y); await pg.waitForTimeout(60); }
    await scrollTo(pg, 0); await pg.waitForTimeout(700);
    const a = await pg.evaluate(measure);
    if (a.nControls === 0 && a.textLen < 40) return { vp: vpName, ok: null, why: 'nothing rendered - UNGRADED' };
    const inkA = keyed(await inkOf(pg, helper));
    const focA = await focusRings(pg, helper);
    await pg.emulateMedia({ forcedColors: 'active' }); await pg.waitForTimeout(900);
    const on = await pg.evaluate(() => matchMedia('(forced-colors: active)').matches);
    if (!on) return { vp: vpName, ok: null, why: 'forced-colors did not engage - UNGRADED' };
    const b = await pg.evaluate(measure);
    const inkB = keyed(await inkOf(pg, helper));
    const focB = await focusRings(pg, helper);
    const both = Object.keys(inkA).filter((k) => k in inkB);
    const vanished = both.filter((k) => inkA[k].ink >= INK_MIN(inkA[k].px) && inkB[k].ink < INK_MIN(inkB[k].px))
      .map((k) => ({ control: k, inkBefore: inkA[k].ink, inkAfter: inkB[k].ink }));
    const ringLost = focB.filter((f) => { const p = focA.find((x) => x.k === f.k && x.name === f.name); return p && p.shown && f.shown === false; })
      .map((f) => ({ control: f.tag + ' ' + f.name, diffBefore: focA.find((x) => x.k === f.k).diff, diffAfter: f.diff }));
    const L = layoutFindings(a, b);
    if (L.reflow) L.culprits = await pg.evaluate(culprits).catch(() => []);
    const ok = !L.reflow && !L.nClipped && !L.nClippedY && !vanished.length && !ringLost.length;
    return { vp: vpName, ok, controlsCompared: both.length, inkBefore: Object.values(inkA).filter((v) => v.ink >= INK_MIN(v.px)).length,
      focusCompared: focB.filter((f) => focA.some((x) => x.k === f.k && x.name === f.name)).length,
      focusShownBefore: focA.filter((f) => f.shown).length, ...L, vanished: vanished.slice(0, 8), nVanished: vanished.length,
      ringLost: ringLost.slice(0, 8), nRingLost: ringLost.length };
  } catch (e) { return { vp: vpName, ok: null, why: 'ERROR ' + String(e.message || e).slice(0, 160) }; }
  finally { await ctx.close().catch(() => {}); }
}

const browser = await chromium.launch({ headless: true });
const hctx = await browser.newContext(); const helper = await hctx.newPage();
const report = existsSync(OUT) ? JSON.parse(readFileSync(OUT, 'utf8')) : { pages: {} };
report.note = 'GROW: 1.4.12 spacing + 200% (desktop: 640x400 viewport; phone: every font-size doubled, width kept). FORCED: '
  + 'forced-colors active, ink and focus read from screenshots. Every finding is differential on one page and one load.';
for (const page of PAGES) {
  const rec = report.pages[page] || {};
  for (const ask of ASKS) {
    const runs = [];
    for (const vp of Object.keys(VIEWPORTS)) runs.push(ask === 'grow' ? await grow(browser, page, vp) : await forced(browser, helper, page, vp));
    const pass = runs.every((r) => r.ok === true) ? true : runs.some((r) => r.ok === false) ? false : null;
    rec[ask] = { pass, runs, ran: new Date().toISOString() };
    const line = runs.map((r) => `${r.vp} ${r.ok === null ? 'UNGRADED ' + (r.why || '') : r.ok ? 'ok' : 'BAD'}`
      + (r.ok === false ? ` [${[r.reflow && `scrolls ${r.docScrollX[1]}px sideways`, r.nClipped && `${r.nClipped} clipped across`,
        r.nClippedY && `${r.nClippedY} clipped down`, r.nLost && `${r.nLost} control(s) lost`, r.nVanished && `${r.nVanished} control(s) vanish`,
        r.nRingLost && `${r.nRingLost} focus ring(s) erased`].filter(Boolean).join(', ')}]` : '')).join(' | ');
    console.log(`${pass === true ? 'PASS' : pass === false ? 'FAIL' : 'UNGR'} ${ask.padEnd(6)} ${page}: ${line}`);
  }
  report.pages[page] = rec;
  report.generated = new Date().toISOString();
  writeFileSync(OUT, JSON.stringify(report, null, 1));       // after every page: a long walk that dies keeps what it measured
}
await browser.close();
const all = Object.entries(report.pages).filter(([p]) => PAGES.includes(p));
const bad = all.flatMap(([p, v]) => ASKS.filter((a) => v[a] && v[a].pass !== true).map((a) => `${p}:${a}`));
console.log(bad.length ? `FAIL text-grows - ${bad.length} page-ask(s) not proven: ${bad.slice(0, 12).join(' ')}`
  : `PASS text-grows - ${all.length} page(s) x ${ASKS.join('+')} at phone-390 and desktop-1280`);
process.exitCode = bad.length ? 1 : 0;
