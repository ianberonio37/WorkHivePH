// Convert marketplace.html inline-SVG icons -> CENTRALIZED icon-library classes (wh-icons.css).
// Emits <span class="ic ic-<name>" aria-hidden="true"></span> — the emoji lives ONCE in wh-icons.css.
// Classifies each <svg> by its distinctive Feather path/points/shape-count (all size variants collapse).
// Run from project root: node tools/emoji_convert_marketplace.mjs
import fs from 'fs';

const FILE = 'marketplace.html';
let t = fs.readFileSync(FILE, 'utf8');

const ic = (name, w) => {
  const size = w > 30 ? ' ic-xl' : w > 18 ? ' ic-lg' : '';
  return `<span class="ic ic-${name}${size}" aria-hidden="true"></span>`;
};

function classify(svg) {
  const w = +((svg.match(/width="(\d+)/) || [])[1] || 14);
  const has = (re) => re.test(svg);
  const lines = (svg.match(/<line\b/g) || []).length;
  const rects = (svg.match(/<rect\b/g) || []).length;

  if (has(/M20\.84 4\.61/))        return ic('save', w);          // heart -> star (watchlist)
  if (has(/points="19 21 12 17/))  return ic('saved', w);         // bookmark
  if (has(/M12 22s8-4 8-10/))      return ic('verified', w);      // shield-check
  if (has(/M7 11V7a5 5/))          return ic('secure', w);        // lock
  if (has(/M2 3h6a4 4/))           return ic('training', w);      // open book
  if (has(/M16 7V5a2 2/))          return ic('jobs', w);          // briefcase
  if (has(/M19\.07 4\.93a10/))     return ic(w <= 12 ? 'admin' : 'parts', w); // gear
  if (has(/points="21 15 16 10/))  return ic('image', w);         // image
  if (has(/points="20 6 9 17/))    return ic('check', w);         // checkmark (text glyph)
  if (has(/M21 10c0 7-9 13/))      return ic('location', w);      // map pin
  if (has(/points="12 6 12 12/))   return ic('free', w);          // clock -> free/no-fees
  if (has(/points="22 2 15 22/))   return ic('send', w);          // paper-plane
  if (has(/M12 4v12m0 0l-4/))      return ic('inventory-in', w);  // down-into-box
  if (has(/M12 2C6\.36 2/))        return ic('message', w);       // messenger bubble
  if (has(/r="?8"?/) && lines === 1)     return ic('search', w);  // magnifier
  if (has(/r="?10"?/) && lines >= 2)     return ic('info', w);    // info-circle
  if (rects === 4)                       return ic('compare', w); // 2x2 grid
  if (lines === 6)                       return ic('list', w);    // list
  if (lines === 3)                       return ic('filter', w);  // filter funnel -> caret
  if (lines === 2) {
    const ls = [...svg.matchAll(/<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"/g)];
    const isPlus = ls.some(m => m[1] === m[3]); // vertical segment => "+"
    return isPlus ? ic('post', w) : ic('close', w);
  }
  return null;
}

let matched = 0; const unmatched = [];
t = t.replace(/<svg[\s\S]*?<\/svg>/g, (svg) => {
  const r = classify(svg);
  if (!r) { unmatched.push(svg.replace(/\s+/g, ' ').slice(0, 60)); return svg; }
  matched++; return r;
});

fs.writeFileSync(FILE, t, 'utf8');
const remaining = (t.match(/<svg\b/g) || []).length;
console.log('matched/replaced:', matched, '| remaining <svg>:', remaining);
if (unmatched.length) { console.log('UNMATCHED:'); [...new Set(unmatched)].forEach(u => console.log('  ', u)); }
