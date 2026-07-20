// Convert leftover HAND-AUTHORED domain inline-SVGs -> emoji, REUSING the walker's own registry.
// utils.js ICONS (name->Lucide path) + MAP (emoji->name) already encode path<->emoji. We invert them
// so a page SVG whose path matches the registry becomes the emoji the platform already assigned it.
// Usage: node tools/emoji_convert_domain.mjs --dry file...   |   --apply file...
import fs from 'fs';

const args = process.argv.slice(2);
const APPLY = args.includes('--apply');
const files = args.filter(a => !a.startsWith('--'));

// --- pull ICONS + MAP object literals out of utils.js and eval (pure data literals) ---
const u = fs.readFileSync('utils.js', 'utf8');
function grabLiteral(src, decl) {
  const start = src.indexOf(decl);
  if (start < 0) return null;
  let i = src.indexOf('{', start), depth = 0, inStr = null, esc = false;
  for (let j = i; j < src.length; j++) {
    const c = src[j];
    if (inStr) { if (esc) esc = false; else if (c === '\\') esc = true; else if (c === inStr) inStr = null; continue; }
    if (c === '"' || c === "'") inStr = c;
    else if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) return src.slice(i, j + 1); }
  }
  return null;
}
const ICONS = new Function('return ' + grabLiteral(u, 'var ICONS'))();
const MAP = new Function('return ' + grabLiteral(u, 'var MAP'))();

// name -> canonical emoji (first colorful emoji in MAP that maps to it; skip mono/glyph fallbacks)
const nameToEmoji = {};
for (const [glyph, v] of Object.entries(MAP)) {
  const name = (typeof v === 'string') ? v : v.n;
  if (!nameToEmoji[name]) nameToEmoji[name] = glyph;               // first wins (MAP order = preference)
}
// registry path-prefix -> emoji  (first <path d="..."> of each ICONS entry)
const pathToEmoji = [];
for (const [name, def] of Object.entries(ICONS)) {
  const emoji = nameToEmoji[name];
  if (!emoji) continue;
  const dm = def.d.match(/d="([^"]{6,})"/) || def.d.match(/<(circle|rect)[^>]*\b(cx|x)="/);
  if (def.d.includes('d="')) { const d = def.d.match(/d="([^"]+)"/)[1]; pathToEmoji.push([d.slice(0, 14), emoji, name]); }
}

const raw = (e) => e; // emoji renders directly (walker disabled)
let grand = 0; const miss = new Map();
for (const FILE of files) {
  if (!fs.existsSync(FILE)) { console.log('skip', FILE); continue; }
  let t = fs.readFileSync(FILE, 'utf8'); let n = 0; const localMiss = [];
  const out = t.replace(/<svg[\s\S]*?<\/svg>/g, (svg) => {
    const d = (svg.match(/\bd="([^"]+)"/) || [])[1] || '';
    const hit = pathToEmoji.find(([p]) => d.startsWith(p));
    if (!hit) { localMiss.push(d.slice(0, 22)); return svg; }
    n++; return `<span class="wh-emo" aria-hidden="true">${raw(hit[1])}</span>`;
  });
  if (APPLY && n) fs.writeFileSync(FILE, out, 'utf8');
  console.log(`${APPLY ? 'APPLIED' : 'DRY'} ${FILE}: convert ${n}, leave ${(out.match(/<svg\b/g) || []).length}`);
  localMiss.forEach(m => miss.set(m, (miss.get(m) || 0) + 1));
  grand += n;
}
console.log(`\nregistry size: ${pathToEmoji.length} icons | total converted: ${grand}`);
const top = [...miss.entries()].sort((a, b) => b[1] - a[1]).slice(0, 20);
if (top.length) { console.log('LEFT (not in registry):'); top.forEach(([m, c]) => console.log(`  x${c} ${m}`)); }
