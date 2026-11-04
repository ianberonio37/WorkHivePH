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
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { chromium } from '@playwright/test';
import { penpot } from './lib/penpot_mcp.mjs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { PAGE_QUERY } from './prover_harness.mjs';

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
// ★THE COMP IS DRAWN AS THE ROW'S CAST (2026-11-04). The first comps read every page signed OUT, so logbook's "comp" was
// the sign-in wall over a dimmed page - a passing diff of the wrong screen. Each OD-P row names its persona: anon walks
// with no session, worker as the seeded worker, oversight and supervisor as the supervisor (prove_csp_exact's mapping),
// through the journeys' own sign-in, and a failed sign-in stops the comp rather than drawing the wall.
const cast = arg('--cast', 'anon');
// ★THE LIVE HALF IS AN MCP READING (2026-11-04). The row's instrument is "penpot-mcp + playwright-mcp + odiff", and the
// first 23 comps compared each board with a screenshot this script's own Playwright LIBRARY took - the ledger rightly
// refused them ([[feedback_a_library_batch_is_not_an_mcp_walk]]). With --live-shots <dir>, the agreement is measured
// against <dir>/<page>@<vp>.png: a full-page screenshot the chrome-devtools MCP took at a true viewport, as the row's
// cast. The library read still supplies the boxes the board is DRAWN from - construction, not evidence. --verify-only
// re-exports the board already in the file instead of redrawing it.
// ★PENPOT STORES A "/" IN A NAME AS ITS PATH SEPARATOR (2026-11-04): "about/index.html @ 390" reads back as
// "about / index.html @ 390", so an exact-name match never found a nested page's board - --verify-only refused all five
// and a redraw left the old board behind beside the new one. Names are compared with the separator's spaces removed.
const SAME_NAME = `((a, b) => a.replace(/\\s*\\/\\s*/g, '/') === b.replace(/\\s*\\/\\s*/g, '/'))`;
const liveShots = arg('--live-shots');
const verifyOnly = process.argv.includes('--verify-only');
const ROLE = cast === 'anon' ? 'anon' : (/supervisor|oversight|owner|engineer|manager/i.test(cast) ? 'supervisor' : 'worker');
if (!page) { console.error('usage: --page <served path> [--cast anon|worker|oversight|supervisor]'); process.exit(2); }

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
    if (ROLE !== 'anon') await assertSignedIn(signIn(ctx, ROLE));
    const p = await ctx.newPage();
    // 'load' and a settle, not 'networkidle': a page holding a realtime socket or polling never goes idle, and twelve
    // signed-in pages timed out at 45s on the first batch without ever being read (2026-11-04)
    await p.goto(`${BASE}/${page}${PAGE_QUERY[page] || ''}`, { waitUntil: 'load', timeout: 60000 });
    await p.waitForTimeout(3500);
    const data = await p.evaluate(({ maxH, maxN }) => {
      const H = Math.min(document.documentElement.scrollHeight, maxH);
      const boxes = [];
      for (const el of document.querySelectorAll('body *')) {
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
        // ★WHAT IS NOT RENDERED IS NOT DRAWN (2026-11-04): the body of a CLOSED <details> keeps its computed display, so
        // logbook's collapsed "How this page works" text was mirrored as ghost lines over the form. checkVisibility()
        // is the browser's own answer, closed <details> and content-visibility included.
        if (typeof el.checkVisibility === 'function'
            && !el.checkVisibility({ contentVisibilityAuto: true, opacityProperty: true, visibilityProperty: true })) continue;
        const r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) continue;
        const y = r.top + scrollY;
        if (y > H) continue;
        // ★A GLOW IS NOT A BLOCK (2026-11-04): analytics-report's decorative orbs are a colour under filter:blur() at a low
        // opacity; mirrored as plain boxes they painted a solid violet and a solid cyan slab and the 1280 comp read 23.6%
        // apart. A heavy blur cannot be drawn by a box mirror, so the box is left out (closer than a slab); every other box
        // carries the opacity it is actually painted at - its own times every ancestor's.
        const blur = /blur\(\s*([\d.]+)px/.exec(cs.filter || '');
        if (blur && +blur[1] >= 12) continue;
        let op = 1;
        for (let a = el; a && a !== document.documentElement; a = a.parentElement) op *= +getComputedStyle(a).opacity || 0;
        if (op < 0.02) continue;
        const bg = /^rgba\(0, 0, 0, 0\)$|transparent/.test(cs.backgroundColor) ? null : cs.backgroundColor;
        const bw = parseFloat(cs.borderTopWidth);
        const border = bw > 0 && !/rgba\(0, 0, 0, 0\)/.test(cs.borderTopColor) ? cs.borderTopColor : null;
        const own = [...el.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim());
        const text = own.map((n) => n.textContent.trim()).join(' ').trim();
        if (!bg && !border && !text) continue;
        // the text sits where ITS glyphs are, not across the whole element: an icon or a padded box beside it otherwise
        // pushes the mirrored text into a narrower wrap ("Log a / Repair" beside its icon)
        let tr = null;
        if (text) {
          const rg = document.createRange(); rg.setStartBefore(own[0]); rg.setEndAfter(own[own.length - 1]);
          const b = rg.getBoundingClientRect();
          if (b.width > 0 && b.height > 0) tr = { x: b.left + scrollX, y: b.top + scrollY, w: b.width + 4, h: b.height };
        }
        boxes.push({ x: r.left + scrollX, y, w: r.width, h: r.height, bg, border, bw: bw || 0, tr, op,
                     radius: parseFloat(cs.borderTopLeftRadius) || 0, text: text.slice(0, 160), color: cs.color,
                     fs: parseFloat(cs.fontSize) || 14, fw: String(cs.fontWeight || '400'),
                     ta: ({ start: 'left', end: 'right', '-webkit-center': 'center' })[cs.textAlign] || cs.textAlign });
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
    for (const s of penpot.currentPage.findShapes()) if (s.type === 'board' && ${SAME_NAME}(s.name, ${JSON.stringify(name)})) s.remove();
    const b = penpot.createBoard(); b.name = ${JSON.stringify(name)}; b.resize(${live.W}, ${live.H});
    const other = penpot.currentPage.findShapes().filter((s) => s.type === 'board' && s.parent && s.parent.type !== 'board');
    b.x = other.reduce((m, s) => Math.max(m, s.x + s.width + 80), 0); b.y = 0;
    const bg = ${JSON.stringify(paint(live.bodyBg))};
    b.fills = bg ? [{ fillColor: bg.hex, fillOpacity: bg.opacity }] : [];
    storage.board = b; storage.bound = 0; storage.errs = 0; storage.firstErr = null;
    // ★ONE SHAPE FAILS ALONE (2026-11-04). A batch is one execute_code script, and an exception the plugin raises comes
    // back as plain text the client cannot tell from a result - so the first throw silently dropped the rest of its
    // 120-shape batch, and logbook's comp read "7 of 90 colours bound" with a 5% pixel diff (the dark board hid it).
    // Each shape is now its own try, and every failure is counted and the first one named in the receipt.
    storage.fail = (e) => { storage.errs++; storage.firstErr = storage.firstErr || String((e && e.message) || e); };
    storage.bind = (shape, c, prop) => { if (!c || !c.token) return; const t = penpotUtils.findTokenByName(c.token);
      if (!t) { storage.fail('no Penpot token named ' + c.token); return; }
      try { t.applyToShapes([shape], [prop]); storage.bound++; } catch (e) { storage.fail(e); } };
    // ★THE COMP IS SET IN THE PAGE'S FACE (2026-11-04). Penpot's default font has no 500 or 800, so every medium and
    // extra-bold label threw "Font weight '500' not supported" (33 of logbook's 218 shapes). WorkHive sets its text in
    // Poppins, which Penpot carries at every weight, so a text is set in Poppins at its own computed weight.
    storage.face = penpot.fonts.findByName('Poppins');
    storage.setFace = (t, fw) => { const f = storage.face; if (!f) { t.fontWeight = fw; return; }
      const v = (f.variants || []).find((x) => String(x.fontWeight) === String(fw) && x.fontStyle !== 'italic');
      f.applyToText(t, v); };
    return b.id;`);
  // ★40 SHAPES A CALL, NOT 120 (2026-11-04): a plugin call runs on Penpot's main thread, so a 120-shape batch on a loaded
  // host held it past the server's 120 s task limit and starved the plugin's own heartbeat ("no heartbeat for 220s"),
  // and every comp queued behind it failed. Smaller calls let the heartbeat run between them.
  const PER_CALL = Number(process.env.PENPOT_SHAPES_PER_CALL || 40);
  for (let i = 0; i < shapes.length; i += PER_CALL) {
    const batch = shapes.slice(i, i + PER_CALL);
    await pp.run(`
      const b = storage.board;
      for (const s of ${JSON.stringify(batch)}) { try {
        if (s.fill || s.stroke) {
          const r = penpot.createRectangle(); b.appendChild(r);
          r.x = b.x + s.x; r.y = b.y + s.y; r.resize(Math.max(1, s.w), Math.max(1, s.h)); r.borderRadius = s.radius;
          r.fills = s.fill ? [{ fillColor: s.fill.hex, fillOpacity: s.fill.opacity }] : [];
          if (s.stroke) r.strokes = [{ strokeColor: s.stroke.hex, strokeOpacity: s.stroke.opacity, strokeWidth: s.bw, strokeAlignment: 'inner' }];
          if (s.op < 1) r.opacity = s.op;   // the layer's painted opacity - fills stay exactly as bound
          storage.bind(r, s.fill, 'fill');
        }
        if (s.text) {
          const t = penpot.createText(s.text); if (!t) continue; b.appendChild(t);
          const tb = s.tr || { x: s.x, y: s.y, w: s.w, h: s.h };
          t.x = b.x + tb.x; t.y = b.y + tb.y; storage.setFace(t, s.fw); t.fontSize = String(Math.round(s.fs));
          t.growType = 'auto-height'; t.resize(Math.max(4, tb.w), Math.max(4, tb.h));
          if (s.ta === 'center' || s.ta === 'right' || s.ta === 'justify') t.align = s.ta;
          if (s.ink) { t.fills = [{ fillColor: s.ink.hex, fillOpacity: s.ink.opacity }]; storage.bind(t, s.ink, 'fill'); }
          if (s.op < 1) t.opacity = s.op;
        }
      } catch (e) { storage.fail(e); } }
      return true;`);
  }
  const { bound, errs, firstErr } = await pp.run('return { bound: storage.bound, errs: storage.errs, firstErr: storage.firstErr };');
  return { name, boardId, boxes: shapes.length, offToken, tokenable: want, bound, errs, firstErr };
}

const report = fs.existsSync(REPORT) ? JSON.parse(fs.readFileSync(REPORT, 'utf8')) : { _doc: '', pages: {} };
report._doc = 'GENERATED by tools/penpot_comp_from_page.mjs - each page unit\'s comp in the WorkHive Penpot file and its '
  + `agreement with the live render (odiff differing-pixel share <= ${MAX_DIFF_PCT}%, every tokenable colour bound).`;
const pp = dry ? null : await penpot();
const out = {};
const safe = page.replace(/[\\/]/g, '_');
for (const vp of vps) {
  let comp, liveShot = path.join('.tmp', 'penpot_comps', `${safe}@${vp}.live.png`);
  if (verifyOnly) {
    const prev = (report.pages[page] || {})[vp];
    if (!prev || !prev.boardId) throw new Error(`--verify-only: no earlier comp of ${page} @ ${vp} in ${REPORT}`);
    const id = await pp.run(`const b = penpot.currentPage.findShapes().find((s) => s.type === 'board' && ${SAME_NAME}(s.name, ${JSON.stringify(prev.name)}));
      if (!b) return null; storage.board = b; return b.id;`);
    if (id !== prev.boardId) throw new Error(`--verify-only: board ${prev.name} is ${id} in the file, ${prev.boardId} in the receipt`);
    const { cast: _c, diffPct: _d, pass: _p, at: _a, live_reader: _r, live_shot: _s, live_sha256: _h, ...kept } = prev;
    comp = kept;
  } else {
    const live = await readLive(vp);
    comp = await buildBoard(pp, vp, live);
    liveShot = live.shot;
  }
  let diffPct = null, reader = 'the Playwright library', mcpSha = null;
  if (!dry) {
    const exported = await pp.run(`const b = storage.board; const bytes = await b.export({ type: 'png', scale: 1 });
      let s = ''; for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]); return btoa(s);`);
    const compPng = path.join('.tmp', 'penpot_comps', `${safe}@${vp}.comp.png`);
    fs.mkdirSync(path.dirname(compPng), { recursive: true });
    fs.writeFileSync(compPng, Buffer.from(exported, 'base64'));
    if (liveShots) {
      const src = path.join(liveShots, `${safe}@${vp}.png`);
      if (!fs.existsSync(src)) throw new Error(`--live-shots: no MCP screenshot at ${src}`);
      mcpSha = crypto.createHash('sha256').update(fs.readFileSync(src)).digest('hex');
      // the MCP's full page, brought to the board's frame: scaled ONLY for a device pixel ratio above 1, cut at the board's
      // height (MAX_HEIGHT), and - when the live page is SHORTER than the board - padded with its own last row, so the
      // missing length still counts as differing pixels against the board's content.
      // ★A SCROLLBAR GUTTER IS NOT A PIXEL RATIO (2026-11-04). Headful Chrome on Windows lays a page out beside a 6px
      // classic scrollbar, so every MCP shot came back 384 or 1274 wide; scaling that to the board's width stretched the
      // page vertically by the same 1.5% and put a 6,600px page 100px out of step at its foot - analytics read 25% apart
      // and every diff doubled. A narrower shot is pasted unscaled and its gutter strip left as background. (The 390 shot
      // is taken with mobile emulation, whose overlay scrollbars lay the page out at the full 390, as a phone does.)
      liveShot = path.join('.tmp', 'penpot_comps', `${safe}@${vp}.mcp.png`);
      execFileSync('python', ['-c', [
        'import sys', 'from PIL import Image',
        'src, ref, dst = sys.argv[1:4]',
        "a = Image.open(src).convert('RGBA'); W, H = Image.open(ref).size",
        'a = a.resize((W, round(a.height * W / a.width)), Image.LANCZOS) if a.width >= W * 1.4 else a',
        "out = Image.new('RGBA', (W, H), a.getpixel((0, a.height - 1)))",
        'out.paste(a.crop((0, 0, min(W, a.width), min(H, a.height))), (0, 0)); out.save(dst)'].join('\n'), src, compPng, liveShot]);
      reader = 'chrome-devtools-mcp';
    }
    const { compare } = await import('odiff-bin');
    const r = await compare(liveShot, compPng, compPng.replace('.comp.png', '.diff.png'), { threshold: 0.1, antialiasing: true });
    diffPct = r.match ? 0 : +(r.diffPercentage ?? 100).toFixed(2);
  }
  const ok = !dry && !comp.errs && comp.bound === comp.tokenable && diffPct !== null && diffPct <= MAX_DIFF_PCT;
  out[vp] = { ...comp, cast, diffPct, pass: ok, at: new Date().toISOString(), live_reader: reader,
              ...(mcpSha ? { live_shot: liveShot.replace(/\\/g, '/'), live_sha256: mcpSha } : {}) };
  console.log(`${page} @ ${vp}: ${comp.boxes} boxes, ${comp.bound ?? '-'}/${comp.tokenable} token-bound, `
    + `${comp.offToken.length} off-token colour(s), diff ${diffPct ?? '-'}% -> ${dry ? 'DRY' : ok ? 'PASS' : 'FAIL'}`
    + (comp.errs ? `  [${comp.errs} shape(s) failed in Penpot; first: ${comp.firstErr}]` : ''));
}
if (!dry) {
  report.pages[page] = { ...(report.pages[page] || {}), ...out };   // one viewport re-verified keeps the other
  fs.writeFileSync(REPORT, JSON.stringify(report, null, 1) + '\n');
}
