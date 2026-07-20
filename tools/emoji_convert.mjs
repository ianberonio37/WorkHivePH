// General emoji-first converter: replaces inline-SVG icons whose Feather path is UNIVERSAL
// (same shape => same concept everywhere) with centralized wh-icons.css classes.
// AMBIGUOUS shapes (gear/book/clock/star/heart) are LEFT and reported for per-page context mapping.
// Usage:  node tools/emoji_convert.mjs --dry file1.html file2.js ...   (report only)
//         node tools/emoji_convert.mjs --apply file1.html ...          (write)
import fs from 'fs';

const args = process.argv.slice(2);
const APPLY = args.includes('--apply');
const files = args.filter(a => !a.startsWith('--'));

// Universal-by-path: the Feather path prefix ALWAYS maps to this concept regardless of page context.
// (Deliberately excludes gear/book/clock/star/heart/box/calendar-grid — those are context-dependent.)
const UNIVERSAL = [
  // closes / X
  ['M6 18L18 6', 'close'], ['M18 6L6 18', 'close'], ['M18 6 6 18', 'close'], ['M6 6l12 12', 'close'],
  // checks
  ['M5 13l4 4L19 7', 'check'], ['M20 6L9 17', 'check'], ['20 6 9 17', 'check'], ['M5 13l4 4L19 6', 'check'],
  ['M16.707 5.293', 'check'], ['M9 12l2 2 4-4', 'check'], ['M9 12l2 2 4-4', 'check'],
  // warning triangle
  ['M12 9v2m0 4h.01m-6.938 4h1', 'warning'], ['M10.29 3.86', 'warning'],
  // search
  ['M21 21l-6-6', 'search'], ['M21 21l-4.35-4.35', 'search'], ['M21 21l-4.3-4.3', 'search'], ['M21 21l-4.34', 'search'],
  // add / plus
  ['M12 4v16m8-8H4', 'add'], ['M12 5v14m-7-7h14', 'add'], ['M12 5v14', 'add'], ['M12 5v14M5 12h14', 'add'],
  // chevrons
  ['M19 9l-7 7-7-7', 'caret'], ['M6 9l6 6 6-6', 'caret'], ['M9 5l7 7-7 7', 'next'], ['M9 18l6-6-6-6', 'next'],
  ['M15 18l-6-6 6-6', 'back'], ['M15 19l-7-7 7-7', 'back'],
  // edit / pencil
  ['M11 5H6a2', 'edit'], ['M11 4H4a2', 'edit'],
  // trash
  ['M3 6h18', 'delete'], ['M19 7l-.867', 'delete'], ['M10 11v6', 'delete'],
  // download / upload
  ['M4 16v1a3', 'download'], ['M21 15v4a2', 'download'],
  // refresh
  ['M18.364 5.636', 'refresh'], ['M23 4v6h-6', 'refresh'], ['M1 4v6h6', 'refresh'],
  // mic / voice
  ['M12 2a3 3', 'voice'], ['M12 1a3 3', 'voice'],
  // camera / image
  ['M23 19a2', 'image'], ['M3 9a2 2 0 012-2h.93', 'image'], ['M4 16l4.586', 'image'],
  // file / doc
  ['M9 12h6m-6 4h6', 'doc'], ['M14 2H6a2 2 0 00-2 2', 'doc'],
  // bell / alert
  ['M18 8a6 6', 'alert'], ['M13.73 21', 'alert'],
  // trust
  ['M12 22s8-4 8-10', 'verified'], ['M7 11V7a5', 'secure'],
  // send / location / message
  ['22 2 15 22', 'send'], ['M22 2L11 13', 'send'], ['M21 10c0 7-9 13', 'location'], ['M17.657 16.657', 'location'],
  ['M21 15a2 2 0 01-2', 'message'],
  // people
  ['M17 20h5v-2', 'community'], ['M17 21v-2a4', 'community'],
  // universal variant paths (different Lucide draws of the same always-one-meaning concept)
  ['M20 7l-8-4-8 4', 'parts'], ['M12 2 L20.5 7', 'parts'], ['M12 2L20.5 7', 'parts'], ['M21 16V8a2 2', 'parts'],
  ['M18 20V10', 'analytics'], ['M3 3v18h18', 'analytics'],
  ['M8 12l3 3 5-6', 'check'], ['M8 12l2 2 4-4', 'check'],
];
const span = (name) => `<span class="ic ic-${name}" aria-hidden="true"></span>`;

let grand = 0; const missAll = new Map();
for (const FILE of files) {
  if (!fs.existsSync(FILE)) { console.log('skip (missing):', FILE); continue; }
  let t = fs.readFileSync(FILE, 'utf8');
  let n = 0; const miss = [];
  const out = t.replace(/<svg[\s\S]*?<\/svg>/g, (svg) => {
    const d = (svg.match(/\bd="([^"]+)"/) || [])[1] || (svg.match(/points="([^"]+)"/) || [])[1] || '';
    const hit = UNIVERSAL.find(([p]) => d.startsWith(p) || svg.includes('"' + p) || svg.includes('points="' + p));
    if (!hit) { miss.push(d.slice(0, 26) || 'shape:' + (svg.match(/<(rect|circle|line|polyline|polygon)/)||[])[1]); return svg; }
    n++; return span(hit[1]);
  });
  const rem = (out.match(/<svg\b/g) || []).length;
  if (APPLY && n) fs.writeFileSync(FILE, out, 'utf8');
  console.log(`${APPLY ? 'APPLIED' : 'DRY'}  ${FILE}: convert ${n}, leave ${rem}`);
  miss.forEach(m => missAll.set(m, (missAll.get(m) || 0) + 1));
  grand += n;
}
console.log(`\n${APPLY ? 'APPLIED' : 'DRY-RUN'} total universal conversions: ${grand}`);
const misses = [...missAll.entries()].sort((a, b) => b[1] - a[1]).slice(0, 30);
if (misses.length) { console.log('TOP LEFT (per-page context needed):'); misses.forEach(([m, c]) => console.log(`  x${c}  ${m}`)); }
