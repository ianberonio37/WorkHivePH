/* audit_symbol_gallery.mjs — T490's evidence engine (2026-09-01).
 * Loads drawing-symbols.js (pure: its only `document.` is in a doc comment) and, using the
 * SAME rendered-discipline list the gallery uses (parsed from symbol-gallery.html's
 * DISCIPLINE_ORDER, not hardcoded), audits every symbol getSymbolList() returns:
 *   - DROPPED: a symbol whose discipline is not one the gallery renders would be silently
 *     omitted (symbol-gallery.html line ~237 `if (!grouped[disc]) continue`) -> gallery INCOMPLETE.
 *   - NONRENDER: a symbol whose render()/drawSymbol() throws or returns no drawable SVG element
 *     paints an empty card -> gallery INACCURATE.
 * Emits JSON. `--self-test` injects one bad-discipline + one empty-render symbol and asserts the
 * audit catches EXACTLY those two (teeth), leaving the real symbols clean.
 */
import fs from 'node:fs';

const SELFTEST = process.argv.includes('--self-test');
const src = fs.readFileSync('drawing-symbols.js', 'utf8');
const api = new Function(src + '; return { list: getSymbolList, draw: drawSymbol, SYMS: DRAWING_SYMBOLS };')();

const gal = fs.readFileSync('symbol-gallery.html', 'utf8');
const m = gal.match(/DISCIPLINE_ORDER\s*=\s*\[([^\]]*)\]/);
const GALLERY_DISC = m ? [...m[1].matchAll(/'([^']+)'/g)].map(x => x[1]) : [];
const DRAWABLE = /<(path|circle|rect|line|polygon|polyline|g|text|ellipse)\b/i;

function audit(list, drawFn) {
  const dropped = [], nonrender = [];
  for (const s of list) {
    if (!GALLERY_DISC.includes(s.discipline)) dropped.push(`${s.key}(${s.discipline})`);
    let svg = '';
    try { svg = drawFn(s.key, 45, 45, s.key === 'instrument' ? { tag: 'PIC', loop: '101' } : {}); }
    catch (e) { svg = 'THREW:' + e.message; }
    if (!(typeof svg === 'string' && DRAWABLE.test(svg))) nonrender.push(`${s.key} -> ${String(svg).slice(0, 40)}`);
  }
  return { total: list.length, disciplines: [...new Set(list.map(s => s.discipline))], gallery_disc: GALLERY_DISC, dropped, nonrender };
}

if (SELFTEST) {
  const list = api.list().concat([
    { key: '__bad_disc__', label: 'x', discipline: '__bogus__' },
    { key: '__empty__',    label: 'y', discipline: GALLERY_DISC[0] },
  ]);
  const draw = (key, ...rest) => key === '__empty__' ? '' : key === '__bad_disc__' ? '<path d="M0 0"/>' : api.draw(key, ...rest);
  const a = audit(list, draw);
  const ok = a.dropped.length === 1 && a.dropped[0].includes('__bad_disc__')
          && a.nonrender.length === 1 && a.nonrender[0].includes('__empty__');
  console.log(JSON.stringify({ selftest: true, ok, dropped: a.dropped, nonrender: a.nonrender }));
  process.exit(ok ? 0 : 1);
}

console.log(JSON.stringify(audit(api.list(), api.draw)));
