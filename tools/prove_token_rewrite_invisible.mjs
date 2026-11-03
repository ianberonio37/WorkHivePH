// prove_token_rewrite_invisible.mjs - a token rewrite must change nothing a person sees (OD-D, 2026-11-03).
//
// tools/fix_token_literals.py rewrites hand-typed token colours as var(--wh-x, <literal>) and rgba(var(--wh-x-rgb, r,g,b),
// a). "Representation only" is a claim; this measures it. Every element's COMPUTED colours - color, background-color,
// border colours, outline-color, box-shadow, text-decoration-color, fill, stroke - are recorded on the served page at
// phone-390 and desktop-1280, before and after; any element whose computed value moved is a rewrite that changed the
// page, and the comparison fails.
//
//   node tools/prove_token_rewrite_invisible.mjs --snap before --pages a.html,b.html
//   ...apply the rewrite...
//   node tools/prove_token_rewrite_invisible.mjs --snap after --pages a.html,b.html --compare before
// Snapshots: .tmp/token_rewrite/<name>.json
import fs from 'node:fs';
import { chromium } from '@playwright/test';

const BASE = process.env.WH_TEST_BASE_URL || 'http://127.0.0.1:5000';
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const snap = arg('--snap');
const pages = (arg('--pages', '') || '').split(',').filter(Boolean);
const against = arg('--compare');
if (!snap || !pages.length) { console.error('usage: --snap <name> --pages a.html,b.html [--compare <name>]'); process.exit(2); }
const DIR = '.tmp/token_rewrite';
fs.mkdirSync(DIR, { recursive: true });
const PROPS = ['color', 'background-color', 'border-top-color', 'border-right-color', 'border-bottom-color',
  'border-left-color', 'outline-color', 'box-shadow', 'text-decoration-color', 'fill', 'stroke', 'background-image'];

const browser = await chromium.launch();
const out = {};
try {
  for (const page of pages) {
    for (const [vp, size] of [['390', { width: 390, height: 844 }], ['1280', { width: 1280, height: 800 }]]) {
      const ctx = await browser.newContext({ viewport: size, deviceScaleFactor: 1, reducedMotion: 'reduce' });
      const p = await ctx.newPage();
      await p.goto(`${BASE}/${page}`, { waitUntil: 'networkidle', timeout: 60000 });
      await p.waitForTimeout(800);
      out[`${page} @ ${vp}`] = await p.evaluate((props) => {
        const rows = [];
        const all = document.querySelectorAll('body, body *');
        for (let i = 0; i < all.length; i++) {
          const el = all[i];
          const cs = getComputedStyle(el);
          // a stable path: tag + index among siblings, up to body (ids and classes can be rewritten by scripts)
          let path = '', n = el;
          while (n && n !== document.body) {
            const idx = n.parentElement ? [...n.parentElement.children].indexOf(n) : 0;
            path = `${n.tagName.toLowerCase()}[${idx}]` + (path ? '>' + path : '');
            n = n.parentElement;
          }
          rows.push([path || 'body', props.map((k) => cs.getPropertyValue(k)).join(' | ')]);
        }
        return rows;
      }, PROPS);
      await ctx.close();
    }
  }
} finally {
  await browser.close();
}
fs.writeFileSync(`${DIR}/${snap}.json`, JSON.stringify(out));
const elements = Object.values(out).reduce((s, r) => s + r.length, 0);
console.log(`snapshot "${snap}": ${pages.length} page(s) x 2 widths, ${elements} element readings`);
// ★A LIVE PAGE MOVES ON ITS OWN (2026-11-03). The first comparison failed 27 readings on status.html and alert-hub.html -
// a status chip amber -> green, a chart's bars swapping orange and blue - and none was the rewrite (amber has no triplet
// the rewrite could reach): the pages colour by LIVE data. --noise <snapA>,<snapB> names two snapshots of the SAME
// unrewritten page; any element that differs between them is the page's own variance and is not compared.
const noisePair = (arg('--noise', '') || '').split(',').filter(Boolean);
const unstable = new Set();
if (noisePair.length === 2) {
  const [na, nb] = noisePair.map((n) => JSON.parse(fs.readFileSync(`${DIR}/${n}.json`, 'utf8')));
  for (const [key, rows] of Object.entries(na)) {
    const other = new Map(nb[key] || []);
    for (const [path, val] of rows) if (!other.has(path) || other.get(path) !== val) unstable.add(`${key} ${path}`);
  }
  console.log(`noise: ${unstable.size} element reading(s) vary between two snapshots of the unrewritten pages - not compared`);
}
if (against) {
  const before = JSON.parse(fs.readFileSync(`${DIR}/${against}.json`, 'utf8'));
  let moved = 0, checked = 0;
  for (const [key, rows] of Object.entries(out)) {
    const prev = new Map(before[key] || []);
    for (const [path, val] of rows) {
      if (!prev.has(path) || unstable.has(`${key} ${path}`)) continue;
      checked++;
      if (prev.get(path) !== val) {
        moved++;
        if (moved <= 12) console.log(`  MOVED ${key} ${path}\n    before: ${prev.get(path)}\n    after:  ${val}`);
      }
    }
  }
  console.log(moved ? `FAIL token-rewrite-invisible: ${moved} of ${checked} element readings changed`
                     : `PASS token-rewrite-invisible: ${checked} element readings identical before and after`);
  process.exit(moved ? 1 : 0);
}
