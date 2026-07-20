// Convert logbook.html + logbook.js OWN inline-SVG icons -> centralized wh-icons.css classes.
// Context-aware: keyed by distinctive Feather path prefix -> semantic class (all map to existing library).
// Run from project root: node tools/emoji_convert_logbook.mjs
import fs from 'fs';

// path-prefix (inside d="...") -> class. Order matters: longer/specific first.
const MAP = [
  ['M12 4v16m8-8H4', 'add'],        ['M12 2a3 3 0 00-3 3v7', 'voice'],
  ['M12 1a3 3 0 00-3 3v8', 'voice'],['M11 5H6a2', 'edit'],
  ['M23 19a2', 'image'],            ['M3 9a2 2 0 012-2h.93', 'image'],
  ['M4 16l4.586', 'image'],         ['M19 9l-7 7', 'caret'],
  ['M3 7V5a2', 'search'],           ['M21 21l-6-6', 'search'],
  ['M9 5H7a2', 'list'],             ['M9 3H5a2', 'list'],
  ['M5 13l4 4L19 7', 'check'],      ['M16.707 5.293', 'check'],
  ['M4 16v1a3', 'download'],        ['M18.364 5.636', 'refresh'],
  ['M9 12h6m-6 4h6m2', 'doc'],      ['M6 18L18 6', 'close'],
  ['M9 5l7 7-7 7', 'next'],         ['M9.049 2.927', 'star'],
  ['M17 20h5v-2a3 3', 'community'],
];
const span = (name) => `<span class="ic ic-${name}" aria-hidden="true"></span>`;

for (const FILE of ['logbook.html', 'logbook.js']) {
  if (!fs.existsSync(FILE)) continue;
  let t = fs.readFileSync(FILE, 'utf8');
  let n = 0; const miss = [];
  t = t.replace(/<svg[\s\S]*?<\/svg>/g, (svg) => {
    const d = (svg.match(/\bd="([^"]+)"/) || [])[1] || (svg.match(/points="([^"]+)"/) || [])[1] || '';
    const hit = MAP.find(([p]) => d.startsWith(p) || svg.includes('d="' + p));
    if (!hit) {
      // fallbacks by shape for pathless icons
      const lines = (svg.match(/<line\b/g) || []).length;
      if (/points="20 6 9 17/.test(svg)) { n++; return span('check'); }
      if (lines === 2 && /x1="18"[^>]*x2="6"/.test(svg)) { n++; return span('close'); }
      miss.push((d || svg.replace(/\s+/g, ' ')).slice(0, 40)); return svg;
    }
    n++; return span(hit[1]);
  });
  fs.writeFileSync(FILE, t, 'utf8');
  const rem = (t.match(/<svg\b/g) || []).length;
  console.log(`${FILE}: converted ${n}, remaining <svg> ${rem}`);
  if (miss.length) { console.log('  MISS:'); [...new Set(miss)].forEach(m => console.log('   ', m)); }
}
