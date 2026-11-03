// penpot_comp_from_page.mjs - a served page's comp in the WorkHive Penpot file, and whether the two agree (OD-P, 2026-11-03).
//
// The OD-P rows ask that each page unit's comp live in the Penpot file, drawn from the token library, and agree with the
// live page (Ian, 2026-11-03: Penpot replaced Figma). The comp is CODE-TO-DESIGN, not drawn by hand: the design source
// stays in code (Ian, 2026-10-13), so the comp is a faithful mirror the designer then edits on the canvas.
//
//   1. Playwright reads the live page (WH_TEST_BASE_URL, default 127.0.0.1:5000) at phone-390 and desktop-1280: every
//      visible box with a background, a border or its own text, with the computed colours, size and weight.
//   2. Each colour is matched to tokens.css. An exact token colour binds the shape's fill to that Penpot token
//      (shape.tokens reads it back). Any other colour is drawn as a literal and REPORTED - that is OD-D's drift, seen.
//   3. The board "<page> @ <viewport>" is (re)built in the open Penpot file (the tab must be connected: MCP -> Connect).
//   4. The board is exported and compared with the live screenshot by odiff (MIT).
//
// A comp closes its OD-P row when: both boards exist (ids in the receipt), every box colour that HAS a token is bound to it,
// and odiff's differing-pixel share is at most MAX_DIFF_PCT. A box-model mirror cannot reproduce icons, images or glyph
// rasterisation, so the bound is a share, not zero; it is wide enough for that and narrow enough that a missing section,
// a wrong background or a shifted column fails.
//
//   node tools/penpot_comp_from_page.mjs --page logbook.html [--viewports 390,1280] [--dry]
//   receipt: penpot_comps_report.json (merged per page)
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from '@playwright/test';
import { penpot } from './lib/penpot_mcp.mjs';

const MAX_DIFF_PCT = 20;
const VIEWPORTS = { 390: { width: 390, height: 844 }, 1280: { width: 1280, height: 800 } };
const MAX_HEIGHT = 6000;
const MAX_BOXES = 700;
const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const REPORT = 'penpot_comps_report.json';

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const page = arg('--page');
const vps = arg('--viewports', '390,1280').split(',').map(Number);
const dry = process.argv.includes('--dry');
if (!page) { console.error('usage: --page <served path>'); process.exit(2); }

// tokens.css :root colours -> 'r,g,b,a' -> token name (flat, as penpot_sync_tokens.mjs writes them)
const css = fs.readFileSync('tokens.css', 'utf8');
const rootCss = css.slice(css.indexOf(':root'), css.indexOf('}', css.indexOf(':root')));
const rgbaKey = (r, g, b, a = 1) => `${Math.round(r)},${Math.round(g)},${Math.round(b)},${(+a).toFixed(2)}`;
const tokenOf = new Map();
for (const m of rootCss.matchAll(/--(wh-[\w-]+)\s*:\s*(#[0-9a-fA-F]{6}|rgba?\([^)]*\))\s*;/g)) {
  const v = m[2];
  let k;
  if (v.startsWith('#')) k = rgbaKey(parseInt(v.slice(1, 3), 16), parseInt(v.slice(3, 5), 16), parseInt(v.slice(5, 7), 16));
  else { const n = v.match(/[\d.]+/g).map(Number); k = rgbaKey(n[0], n[1], n[2], n[3] ?? 1); }
  if (!tokenOf.has(k)) tokenOf.set(k, m[1]);
}
const parseCss = (c) => { const n = (c || '').match(/[\d.]+/g); return n ? n.map(Number) : null; };
const hex = (n) => '#' + n.slice(0, 3).map((x) => Math.round(x).toString(16).padStart(2, '0')).join('').toUpperCase();
function paint(c) {
  const n = parseCss(c);
  if (!n || (n.length > 3 && n[3] === 0)) return null;
  const a = n.length > 3 ? n[3] : 1;
  return { hex: hex(n), opacity: a, token: tokenOf.get(rgbaKey(n[0], n[1], n[2], a)) || null };
}

async function readLive(vp) {
  const browser = await chromium.launch();
  try {
    const ctx = await browser.newContext({ viewport: VIEWPORTS[vp], deviceScaleFactor: 1 });
    const p = await ctx.newPage();
    await p.goto(`${BASE}/${page}`, { waitUntil: 'networkidle', timeout: 45000 });
    await p.waitForTimeout(1200);
    const data = await p.evaluate(({ maxH, maxN }) => {
      const H = Math.min(document.documentElement.scrollHeight, maxH);
      const boxes = [];
      for (const el of document.querySelectorAll('body *')) {
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) continue;
        const y = r.top + scrollY;
        if (y > H) continue;
        const bg = /^rgba\(0, 0, 0, 0\)$|transparent/.test(cs.backgroundColor) ? null : cs.backgroundColor;
        const bw = parseFloat(cs.borderTopWidth);
        const border = bw > 0 && !/rgba\(0, 0, 0, 0\)/.test(cs.borderTopColor) ? cs.borderTopColor : null;
        const text = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join(' ').trim();
        if (!bg && !border && !text) continue;
        boxes.push({ x: r.left + scrollX, y, w: r.width, h: r.height, bg, border, bw: bw || 0,
                     radius: parseFloat(cs.borderTopLeftRadius) || 0, text: text.slice(0, 160), color: cs.color,
                     fs: parseFloat(cs.fontSize) || 14, fw: String(cs.fontWeight || '400') });
        if (boxes.length >= maxN) break;
      }
      return { W: innerWidth, H, bodyBg: getComputedStyle(document.body).backgroundColor, boxes };
    }, { maxH: MAX_HEIGHT, maxN: MAX_BOXES });
    const shot = path.join('.tmp', 'penpot_comps', `${page.replace(/[\\/]/g, '_')}@${vp}.live.png`);
    fs.mkdirSync(path.dirname(shot), { recursive: true });
    await p.screenshot({ path: shot, clip: { x: 0, y: 0, width: data.W, height: data.H }, fullPage: true });
    return { ...data, shot };
  } finally {
    await browser.close();
  }
}

async function buildBoard(pp, vp, live) {
  const name = `${page} @ ${vp}`;
  const shapes = live.boxes.map((b) => ({ ...b, fill: b.bg ? paint(b.bg) : null, stroke: b.border ? paint(b.border) : null,
                                          ink: b.text ? paint(b.color) : null }));
  const offToken = [...new Set(shapes.flatMap((s) => [s.fill, s.stroke, s.ink]).filter((c) => c && !c.token).map((c) => c.hex))];
  const want = shapes.flatMap((s) => [s.fill, s.ink]).filter((c) => c && c.token).length;
  if (dry) return { name, boxes: shapes.length, offToken, tokenable: want };
  // one board per call keeps each execute_code payload bounded; shapes go in batches through `storage`
  const boardId = await pp.run(`
    for (const s of penpot.currentPage.findShapes()) if (s.type === 'board' && s.name === ${JSON.stringify(name)}) s.remove();
    const b = penpot.createBoard(); b.name = ${JSON.stringify(name)}; b.resize(${live.W}, ${live.H});
    const other = penpot.currentPage.findShapes().filter((s) => s.type === 'board' && s.parent && s.parent.type !== 'board');
    b.x = other.reduce((m, s) => Math.max(m, s.x + s.width + 80), 0); b.y = 0;
    const bg = ${JSON.stringify(paint(live.bodyBg))};
    b.fills = bg ? [{ fillColor: bg.hex, fillOpacity: bg.opacity }] : [];
    storage.board = b; storage.bound = 0;
    storage.bind = (shape, c, prop) => { if (!c || !c.token) return; const t = penpotUtils.findTokenByName(c.token);
      if (t) { t.applyToShapes([shape], [prop]); storage.bound++; } };
    return b.id;`);
  for (let i = 0; i < shapes.length; i += 120) {
    const batch = shapes.slice(i, i + 120);
    await pp.run(`
      const b = storage.board;
      for (const s of ${JSON.stringify(batch)}) {
        if (s.fill || s.stroke) {
          const r = penpot.createRectangle(); b.appendChild(r);
          r.x = b.x + s.x; r.y = b.y + s.y; r.resize(Math.max(1, s.w), Math.max(1, s.h)); r.borderRadius = s.radius;
          r.fills = s.fill ? [{ fillColor: s.fill.hex, fillOpacity: s.fill.opacity }] : [];
          if (s.stroke) r.strokes = [{ strokeColor: s.stroke.hex, strokeOpacity: s.stroke.opacity, strokeWidth: s.bw, strokeAlignment: 'inner' }];
          storage.bind(r, s.fill, 'fill');
        }
        if (s.text) {
          const t = penpot.createText(s.text); if (!t) continue; b.appendChild(t);
          t.x = b.x + s.x; t.y = b.y + s.y; t.fontSize = String(Math.round(s.fs)); t.fontWeight = s.fw;
          t.growType = 'auto-height'; t.resize(Math.max(4, s.w), Math.max(4, s.h));
          if (s.ink) { t.fills = [{ fillColor: s.ink.hex, fillOpacity: s.ink.opacity }]; storage.bind(t, s.ink, 'fill'); }
        }
      }
      return true;`);
  }
  const bound = await pp.run('return storage.bound;');
  return { name, boardId, boxes: shapes.length, offToken, tokenable: want, bound };
}

const report = fs.existsSync(REPORT) ? JSON.parse(fs.readFileSync(REPORT, 'utf8')) : { _doc: '', pages: {} };
report._doc = 'GENERATED by tools/penpot_comp_from_page.mjs - each page unit\'s comp in the WorkHive Penpot file and its '
  + `agreement with the live render (odiff differing-pixel share <= ${MAX_DIFF_PCT}%, every tokenable colour bound).`;
const pp = dry ? null : await penpot();
const out = {};
for (const vp of vps) {
  const live = await readLive(vp);
  const comp = await buildBoard(pp, vp, live);
  let diffPct = null;
  if (!dry) {
    const exported = await pp.run(`const b = storage.board; const bytes = await b.export({ type: 'png', scale: 1 });
      let s = ''; for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]); return btoa(s);`);
    const compPng = live.shot.replace('.live.png', '.comp.png');
    fs.writeFileSync(compPng, Buffer.from(exported, 'base64'));
    const { compare } = await import('odiff-bin');
    const r = await compare(live.shot, compPng, live.shot.replace('.live.png', '.diff.png'), { threshold: 0.1, antialiasing: true });
    diffPct = r.match ? 0 : +(r.diffPercentage ?? 100).toFixed(2);
  }
  const ok = !dry && comp.bound === comp.tokenable && diffPct !== null && diffPct <= MAX_DIFF_PCT;
  out[vp] = { ...comp, diffPct, pass: ok, at: new Date().toISOString() };
  console.log(`${page} @ ${vp}: ${comp.boxes} boxes, ${comp.bound ?? '-'}/${comp.tokenable} token-bound, `
    + `${comp.offToken.length} off-token colour(s), diff ${diffPct ?? '-'}% -> ${dry ? 'DRY' : ok ? 'PASS' : 'FAIL'}`);
}
if (!dry) {
  report.pages[page] = out;
  fs.writeFileSync(REPORT, JSON.stringify(report, null, 1) + '\n');
}
