// Convert the remaining shared-component inline SVGs -> centralized wh-icons.css classes.
// Small, specific icon sets per file. Run from project root: node tools/emoji_convert_shared.mjs
import fs from 'fs';

const FILES = ['companion-launcher.js', 'wayfinding.js', 'search-overlay.js', 'voice-handler.js'];
const span = (name) => `<span class="ic ic-${name}" aria-hidden="true"></span>`;

function classify(svg) {
  const has = (re) => re.test(svg);
  const lines = (svg.match(/<line\b/g) || []).length;
  if (has(/M22 2L11 13/) || has(/M22 2L15 22/)) return 'send';        // paper-plane
  if (has(/M12 1a3 3/) && lines >= 2)          return 'voice';        // microphone
  if (has(/M12 8v4l3 3/) || has(/M12 7v5/))    return 'clock';        // clock face
  if (has(/points="15 18 9 12/))               return 'back';         // left chevron
  if (has(/r="?8"?/) && lines <= 1 && has(/circle/)) return 'search'; // magnifier
  return null;
}

let total = 0;
for (const f of FILES) {
  if (!fs.existsSync(f)) continue;
  let t = fs.readFileSync(f, 'utf8');
  let n = 0; const miss = [];
  t = t.replace(/<svg[\s\S]*?<\/svg>/g, (svg) => {
    const cls = classify(svg);
    if (!cls) { miss.push(svg.replace(/\s+/g, ' ').slice(0, 60)); return svg; }
    n++; return span(cls);
  });
  fs.writeFileSync(f, t, 'utf8');
  const rem = (t.match(/<svg\b/g) || []).length;
  console.log(`${f}: replaced ${n}, remaining <svg> ${rem}${miss.length ? ' MISS:' + miss.join(' | ') : ''}`);
  total += n;
}
console.log('TOTAL shared-component icons converted:', total);
