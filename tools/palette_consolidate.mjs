// Palette consolidation ("follow my theme brand"): fold each ACCENT hex onto its own hue-family's
// brand canonical. Skips NEUTRALS (low-sat greys/navies) + near-white/near-black surfaces + semantic
// TINT backgrounds (very light) — those carry surface/meaning, never blind-folded to a neutral.
// Usage: node tools/palette_consolidate.mjs --dry|--apply [only=orange,blue]
import fs from 'fs';

const args = process.argv.slice(2);
const APPLY = args.includes('--apply');
const ONLY = (args.find(a => a.startsWith('only=')) || '').slice(5).split(',').filter(Boolean);

// hue-family -> canonical brand hex (tokens.css brand where defined; else the platform's dominant use)
const CANON = {
  orange: '#f7a21b',   // --wh-orange
  amber:  '#facc15',   // semantic warn (dominant)
  green:  '#4ade80',   // semantic good (platform-dominant, 191x)
  blue:   '#29b6d9',   // --wh-blue
  violet: '#a78bfa',   // brand lilac / AI accent (dominant)
  red:    '#f87171',   // semantic alert (dominant bg/icon; AA-text --wh-red-text #fca5a5 kept)
};
// tokens.css AA-tuned / explicit brand values that must NOT be folded away (kept verbatim).
// #7c3aed = the brand purple a step DARKER, chosen for AA on WHITE/print surfaces (designer .doc-logo
// lesson) — folding it to the lighter #a78bfa would drop it below 4.5:1 on light. Keep it.
const KEEP = new Set(['#fca5a5', '#c4b5fd', '#d88a0e', '#fdb94a', '#1a9abf', '#5fcce8', '#7c3aed']);

function hsl(hex) {
  const r = parseInt(hex.slice(1, 3), 16) / 255, g = parseInt(hex.slice(3, 5), 16) / 255, b = parseInt(hex.slice(5, 7), 16) / 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn;
  let h = 0, s = 0;
  if (d) {
    s = l > .5 ? d / (2 - mx - mn) : d / (mx + mn);
    h = mx === r ? ((g - b) / d + (g < b ? 6 : 0)) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h *= 60;
  }
  return { h, s, l };
}
function family(hex) {
  const { h, s, l } = hsl(hex);
  // ONLY fold BRIGHT, saturated ACCENTS. Skip dark SURFACES/borders (L<.35 — e.g. navy #162032 is
  // blue-hued but is the page background, NOT an accent), light TINTS (L>.85 — semantic bg tints), and
  // low-sat neutrals (greys/navies handled by steel/navy tokens, never blind-folded to an accent).
  if (l < .35 || l > .82) return null;
  if (s < 0.32) return null;
  if (h < 18 || h >= 320) return 'red';       // includes pink/magenta (320-360)
  if (h < 45) return 'orange';
  if (h < 70) return 'amber';
  if (h < 170) return 'green';
  if (h < 205) return 'blue';                 // cyan+blue
  if (h < 250) return 'blue';                 // slate-blue → brand blue
  if (h < 320) return 'violet';
  return null;
}

const files = fs.readdirSync('.').filter(f => /\.(html|css)$/.test(f) && !/\.bak|backup|-test|_tw_extract/.test(f));
const hexRe = /#[0-9a-fA-F]{6}\b/g;
const folds = {}; const perFam = {}; let total = 0;

for (const f of files) {
  let t = fs.readFileSync(f, 'utf8'); let n = 0;
  const out = t.replace(hexRe, (raw) => {
    const h = raw.toLowerCase();
    if (KEEP.has(h)) return raw;
    const fam = family(h);
    if (!fam || (ONLY.length && !ONLY.includes(fam))) return raw;
    const target = CANON[fam];
    if (h === target) return raw;             // already canonical
    folds[h] = `${target} (${fam})`; perFam[fam] = (perFam[fam] || 0) + 1; n++; total++;
    return APPLY ? target : raw;
  });
  if (APPLY && n) fs.writeFileSync(f, out, 'utf8');
}

console.log(`${APPLY ? 'APPLIED' : 'DRY'}${ONLY.length ? ' only=' + ONLY.join(',') : ''} · folded ${total} occurrences · ${Object.keys(folds).length} distinct → brand`);
console.log('per-family occurrences:', JSON.stringify(perFam));
console.log('\n--- distinct folds (stray → family canonical) ---');
Object.entries(folds).sort().forEach(([h, to]) => console.log(`  ${h} → ${to}`));
