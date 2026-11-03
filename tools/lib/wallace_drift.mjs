// wallace_drift.mjs - the design-source lens's measuring instrument (2026-11-03).
//
// Project Wallace's css-analyzer (MIT, github.com/projectwallace/css-analyzer) parses CSS the way a browser would and
// counts every value it holds. This helper hands it each file's own CSS and sorts every colour literal by what
// tokens.css says about it:
//   exact  the literal IS a token's colour           -> it should be var(--token)
//   tint   a token's RGB at an alpha                 -> it should be rgba(var(--token-rgb), a)
//   off    an RGB the palette does not have          -> drift, or a token the system is missing
// and counts the raw (non-var) font sizes, font families and z-indexes. A literal inside var(--x, <fallback>) is
// excused: the shared chrome loads tokens.css async, so the fallback is the first-paint safety net, not a choice
// (the rule component_purity_census.py already holds).
//
// stdin:  {"tokens": "<tokens.css text>", "items": [{"file": "...", "css": "..."}]}
// stdout: {"palette": N, "files": {"<file>": {exact, tint, off, offRgbs, fontSizes, families, zIndexes}}}
import { analyze } from '@projectwallace/css-analyzer';
import { pathToFileURL } from 'node:url';

const NAMED = { white: [255, 255, 255, 1], black: [0, 0, 0, 1] };

export function rgbOf(c) {
  const v = String(c).trim().toLowerCase();
  if (NAMED[v]) return NAMED[v];
  let m = /^#([0-9a-f]{3,8})$/.exec(v);
  if (m) {
    let h = m[1];
    if (h.length === 5 || h.length === 7) return null;
    if (h.length <= 4) h = [...h].map((x) => x + x).join('');
    const a = h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1;
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), +a.toFixed(3)];
  }
  m = /^rgba?\(([^)]*)\)$/.exec(v);
  if (m) {
    if (/var\(/.test(m[1])) return null; // rgba(var(--wh-orange-rgb), .2) is already on the system
    const n = m[1].split(/[\s,/]+/).filter(Boolean).map((x) => (x.endsWith('%') ? parseFloat(x) / 100 : parseFloat(x)));
    if (n.length < 3 || n.some(Number.isNaN)) return null;
    return [n[0], n[1], n[2], n.length > 3 ? n[3] : 1];
  }
  return null;
}

const key = (r) => r.slice(0, 3).join(',');

const fullKey = (r) => `${r.slice(0, 3).join(',')},${(+r[3]).toFixed(2)}`;

export function palette(tokensCss) {
  const out = new Map();
  // ★a token's FULL value, alpha included: rgba(255,255,255,0.80) IS --wh-text-muted, so a page typing it is 'exact'
  // (use the token), not a 'tint' (439 uses on the first reading were misfiled as tints before this)
  out.exact = new Set();
  for (const m of tokensCss.matchAll(/(--[\w-]+)\s*:\s*([^;{}]+);/g)) {
    const v = m[2].trim();
    const c = rgbOf(v);
    const r = c || (/^\d+\s*,\s*\d+\s*,\s*\d+$/.test(v) ? [...v.split(',').map(Number), 1] : null);
    if (c) out.exact.add(fullKey(c));
    if (r && !out.has(key(r))) out.set(key(r), m[1]);
  }
  return out;
}

// var(--x, <anything, one level of parens>) -> var(--x): the fallback is excused
export const stripFallbacks = (css) => css.replace(/var\(\s*(--[\w-]+)\s*,(?:[^()]|\([^()]*\))*\)/g, 'var($1)');

const SKIP = /^(transparent|currentcolor|inherit|initial|unset|none|revert)$/i;
const rawCount = (o) => Object.keys((o && o.unique) || {}).filter((v) => !/var\(/.test(v)).length;

export function measure(css, pal) {
  const r = analyze(stripFallbacks(css));
  const out = { exact: 0, tint: 0, neutral: 0, off: 0, offRgbs: [] };
  const offs = new Set();
  for (const [lit, n] of Object.entries(r.values.colors.unique || {})) {
    // ★a colour built FROM a token (rgba(var(--wh-orange-rgb), .2)) is the on-system form; the self-test caught the
    // first draft counting it as off-palette because rgbOf() cannot resolve a var().
    if (SKIP.test(lit) || /var\(/.test(lit)) continue;
    const c = rgbOf(lit);
    if (!c) { out.off += n; offs.add(lit.toLowerCase()); continue; } // a named or hsl colour: not on the palette
    if ((pal.exact && pal.exact.has(fullKey(c))) || (pal.has(key(c)) && c[3] >= 1)) out.exact += n;
    else if (pal.has(key(c))) out.tint += n;
    // ★black and white at an alpha are shadows and scrims (152 files on the first reading) - a scale the system does
    // not own yet, but not palette drift; counted apart so they cannot bury the real off-palette colours.
    else if (key(c) === '0,0,0' || key(c) === '255,255,255') out.neutral += n;
    else { out.off += n; offs.add(key(c)); }
  }
  out.offRgbs = [...offs].sort();
  out.fontSizes = rawCount(r.values.fontSizes);
  out.families = rawCount(r.values.fontFamilies);
  out.zIndexes = rawCount(r.values.zindexes);
  return out;
}

const isMain = !!process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  let raw = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (d) => { raw += d; });
  process.stdin.on('end', () => {
    const { tokens, items } = JSON.parse(raw);
    const pal = palette(tokens);
    const files = {};
    for (const { file, css } of items) files[file] = measure(css, pal);
    process.stdout.write(JSON.stringify({ palette: pal.size, files }));
  });
}
