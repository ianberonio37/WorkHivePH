// Fix the L3 raw-brand-hex regression from the palette fold: migrate brand hexes -> var(--wh-*)
// in CSS contexts only (<style> blocks in HTML + .css files), SKIP <script> (JS color strings can't
// resolve CSS vars) and tokens.css (it DEFINES the hexes). This both clears L3 and centralizes properly.
// Usage: node tools/hex_to_var.mjs --dry|--apply
import fs from 'fs';
const APPLY = process.argv.includes('--apply');

const MAP = {
  '#f7a21b': '--wh-orange', '#d88a0e': '--wh-orange-dark', '#fdb94a': '--wh-orange-light',
  '#29b6d9': '--wh-blue', '#1a9abf': '--wh-blue-dark', '#5fcce8': '--wh-blue-light',
  '#4ade80': '--wh-green', '#f87171': '--wh-red', '#facc15': '--wh-amber', '#a78bfa': '--wh-violet',
  '#162032': '--wh-navy', '#1f2e45': '--wh-navy-mid', '#2a3d58': '--wh-navy-light',
  '#7b8794': '--wh-steel', '#a9b6c4': '--wh-steel-bright',
  '#fca5a5': '--wh-red-text', '#c4b5fd': '--wh-violet-text', '#f4f6fa': '--wh-cloud',
};
const migrate = (css) => css.replace(/#[0-9a-fA-F]{6}\b/g, (h) => {
  const v = MAP[h.toLowerCase()];
  return v ? `var(${v})` : h;
});

const files = fs.readdirSync('.').filter(f => /\.(html|css)$/.test(f) && !/\.bak|backup|-test|_tw_extract|tokens\.css/.test(f));
let total = 0;
for (const f of files) {
  let t = fs.readFileSync(f, 'utf8'); const before = (t.match(/#[0-9a-fA-F]{6}/g) || []).length;
  let out;
  if (f.endsWith('.css')) {
    out = migrate(t);
  } else {
    // HTML: migrate inside <style>...</style> blocks + every style="..." attribute (both are CSS —
    // a style attr renders as CSS even inside a JS template string, so var() resolves). Bare JS color
    // strings (color:'#hex' passed to a chart lib) are left — they can't resolve a CSS var.
    out = t.replace(/<style\b[^>]*>[\s\S]*?<\/style>/g, (blk) => migrate(blk));
    out = out.replace(/style="([^"]*)"/g, (m, css) => `style="${migrate(css)}"`);
    out = out.replace(/style='([^']*)'/g, (m, css) => `style='${migrate(css)}'`);
  }
  const after = (out.match(/#[0-9a-fA-F]{6}/g) || []).length;
  const converted = before - after;
  if (APPLY && converted) fs.writeFileSync(f, out, 'utf8');
  if (converted) { console.log(`${APPLY ? 'APPLIED' : 'DRY'} ${f}: ${converted} brand-hex → var`); total += converted; }
}
console.log(`\ntotal brand-hex → var: ${total}`);
