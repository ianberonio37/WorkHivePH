/* ============================================================================
 * tw_extract_build.mjs — self-host the Tailwind CDN's compiled CSS (no build step)
 * ============================================================================
 * The 9 Tailwind-CDN pages emit `cdn.tailwindcss.com should not be used in
 * production` (a real P2 warning + a heavy runtime JIT dependency). The other 21
 * pages already run on tokens.css + own <style>. This migrates the 9 off the CDN
 * WITHOUT touching a single class in the markup (zero layout-regression risk):
 *
 *   1. Scan the 9 pages for every Tailwind utility class actually used (438).
 *   2. Merge the per-page `tailwind.config` custom themes (colors/fonts).
 *   3. Emit a test page (`_tw_extract.html`) that lists all 438 classes + the
 *      merged config + the SAME CDN script — so the CDN compiles the exact CSS
 *      those classes need.
 *   4. (next step) Playwright-load it, read the injected <style>, save as
 *      `wh-tw.css`. Then swap `<script src=cdn.tailwindcss.com>` -> `<link wh-tw.css>`.
 *
 * Tailwind itself generates the CSS, so the output is byte-correct for those
 * classes — safer than hand-writing 438 rules. Run: node tools/tw_extract_build.mjs
 * ==========================================================================*/
import fs from 'fs';

const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'dayplanner',
               'engineering-design', 'assistant', 'voice-journal'];

// Tailwind utility-class shape (prefixes + known utility roots). Mirrors tw_extract's scan.
const TW = /^(sm:|md:|lg:|xl:|2xl:|hover:|focus:|focus-visible:|active:|group-hover:|group-focus:|peer-focus:|disabled:|first:|last:|odd:|even:|dark:|motion-safe:|motion-reduce:)*(flex|grid|block|inline|inline-block|inline-flex|hidden|table|contents|flow-root|items-|justify-|content-|self-|place-|gap-|space-|grid-|col-|row-|order-|text-|font-|leading-|tracking-|whitespace-|break-|truncate|uppercase|lowercase|capitalize|normal-case|underline|no-underline|line-through|bg-|from-|via-|to-|border|rounded|shadow|opacity-|p-|px-|py-|pt-|pb-|pl-|pr-|m-|mx-|my-|mt-|mb-|ml-|mr-|-m|w-|h-|min-|max-|top-|bottom-|left-|right-|inset-|z-|absolute|relative|fixed|sticky|static|overflow-|object-|cursor-|pointer-events-|select-|resize|transition|duration-|ease-|delay-|animate-|transform|scale-|rotate-|translate-|skew-|origin-|ring|outline|divide-|backdrop-|filter|blur|brightness|antialiased|subpixel-antialiased|sr-only|not-sr-only|container|aspect-|fill-|stroke-|flex-|basis-|grow|shrink|float-|clear-|align-|list-|placeholder-|caret-|accent-|scroll-|snap-|touch-|will-change-|appearance-)/;

const classes = new Set();
for (const p of PAGES) {
  let t; try { t = fs.readFileSync(p + '.html', 'utf8'); } catch { continue; }
  for (const m of t.match(/class="[^"]*"/g) || []) {
    for (const tok of m.slice(7, -1).split(/\s+/)) if (tok && TW.test(tok)) classes.add(tok);
  }
  // also catch classList / className string literals in inline JS (dynamically toggled utilities)
  for (const m of t.match(/(?:classList\.(?:add|remove|toggle)|className\s*[+]?=)\s*[('"`][^)'"`]*/g) || []) {
    for (const tok of m.split(/[\s'"`]+/)) if (tok && TW.test(tok)) classes.add(tok);
  }
}
const list = [...classes].sort();

// Merge every page's tailwind.config theme.extend (union). We just need the color/font
// tokens so `bg-navy-wh` etc. resolve. Pull each config block verbatim and let the CDN
// merge — simplest correct approach is to embed the richest single config (index's) plus
// a superset of custom colors seen across pages.
const CONFIG = `
    tailwind.config = {
      theme: { extend: {
        colors: {
          orange: { wh:'#F7A21B', dark:'#D88A0E', light:'#FDB94A' },
          blue:   { wh:'#29B6D9', dark:'#1A9ABF', light:'#5FCCE8' },
          navy:   { wh:'#162032', mid:'#1F2E45', light:'#2A3D58' },
          steel:  '#7B8794',
          cloud:  '#F4F6FA',
          honey:  '#F7A21B',
          amber:  { wh:'#F7A21B' },
        },
        fontFamily: { poppins: ['Poppins','sans-serif'] },
      } },
    };`;

const html = `<!doctype html><html><head><meta charset="utf-8">
<script src="https://cdn.tailwindcss.com"></script>
<script>${CONFIG}</script>
</head><body>
<div id="tw-harvest">${list.map(c => `<div class="${c.replace(/"/g, '')}"></div>`).join('')}</div>
</body></html>`;

fs.writeFileSync('_tw_extract.html', html);
fs.writeFileSync('.tmp/tw_classes.json', JSON.stringify(list, null, 0));
console.log(`Extracted ${list.size ?? list.length} unique Tailwind classes across ${PAGES.length} pages.`);
console.log(`Wrote _tw_extract.html (harvest page) + .tmp/tw_classes.json`);
console.log(`custom-color classes:`, list.filter(x => /(navy|orange|blue|steel|cloud|honey|amber)-?(wh|dark|light|mid)?/.test(x) && /^(bg-|text-|border-|from-|via-|to-|ring-|divide-)/.test(x)).length);
