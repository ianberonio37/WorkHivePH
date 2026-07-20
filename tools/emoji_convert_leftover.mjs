// Convert the leftover per-page ICON-svgs -> emoji on the 11 icon_floor pages (drive I-lens -> 0).
// aria-label match first (reliable), then path-prefix. Diagrams (dynamic viewBox) are never touched.
// Usage: node tools/emoji_convert_leftover.mjs --dry|--apply
import fs from 'fs';
const APPLY = process.argv.includes('--apply');
const PAGES = ['index.html','inventory.html','dayplanner.html','hive.html','pm-scheduler.html','community.html','assistant.html','asset-hub.html','skillmatrix.html','achievements.html','marketplace-seller.html','marketplace-admin.html','marketplace-seller-profile.html','shift-brain.html','report-sender.html'];
const span = n => `<span class="ic ic-${n}" aria-hidden="true"></span>`;

// aria-label substring -> class (checked on the <svg ...> opening tag AND the wrapping button/a if present)
const ARIA = [
  [/show password|hide password/i,'eye'],[/copy link/i,'link'],[/pin post|unpin/i,'pin'],
  [/make post (public|private)/i,'globe'],[/flag post|unflag/i,'flag'],[/report this/i,'warning'],
  [/back|collapse sidebar/i,'back'],[/refresh|reload/i,'refresh'],[/search/i,'search'],
  [/notification|alert/i,'bell'],[/settings|configure/i,'settings'],[/help/i,'help'],
];
// path prefix -> class (from inventory; distinctive Feather draws)
const PATH = [
  ['15 18 9 12','back'],['M11 19l-7-7','back'],['M3 12l2-2','home'],
  ['M8 14h.01M12 14','calendar'],['M8 7V3m8 4V3','calendar'],
  ['M10 18a8 8','clock'],['M18 10a8 8','clock'],['M12 8v4l3 3','clock'],
  ['M15 17h5','bell'],['M12 6V4m0 2','settings'],
  ['M15 12a3 3','eye'],['M21 12a9 9','help'],['M20 12H4','minus'],['M19 11H5','minus'],
  ['M9 5H7a2 2','list'],['M9 3H5a2 2','list'],['M9.049 2.927','star'],
  ['M8.257 3.099','warning'],['M12 9v2m0 4','warning'],['M4 4v5','refresh'],
  ['M13 7l5 5','next'],['M3 7V5a2 2','scan'],['M13.828 10.172','link'],
  ['M5 5a2 2','pin'],['M3.055 11H5','globe'],['M3 21v-4','flag'],['M9 19v-6','analytics'],
  ['M10.325 4.317','ai-spark'],['M7 7h.01M7 3h5','list'],
  ['21 15 16 10','image'],['M12 19l9 2-9-18','send'],['M12 2C6.36 2','message'],
  ['8.21 13.89','star'],['M8 12h.01M12 12','list'],['M12 2a15.3 15.3','globe'],
  ['M12 2 L2','send'],['M22 2L11 13','send'],
  // index.html industry-sector set (mapped by their distinctive paths)
  ['M10.394 2.08','factory'],['M11.3 1.046','power'],['M2 11a1','food'],
  ['M4 2a2 2','chip'],['M9 6a3 3','building'],['M3 5a2 2','oil'],
  // marketplace-seller
  ['M20 21v-2a4','user'],['12 19 5 12','saved'],
];
// shape-only (no path d) icons: classify by <line> count + orientation
function shapeClass(svg) {
  const lines = [...svg.matchAll(/<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"/g)];
  if (svg.includes('<polyline') || svg.includes('<polygon')) return null;
  if (lines.length >= 5) return 'list';
  if (lines.length === 3) return 'filter';
  if (lines.length === 2) return lines.some(m => m[1] === m[3]) ? 'post' : 'close'; // vertical seg => +
  return null;
}

let matched = 0; const miss = new Map();
for (const f of PAGES) {
  if (!fs.existsSync(f)) continue;
  let t = fs.readFileSync(f, 'utf8'); let n = 0;
  const out = t.replace(/<svg[\s\S]*?<\/svg>/g, (svg, off) => {
    const vb = (svg.match(/viewBox="([^"]*)"/) || [])[1] || '';
    const w = (svg.match(/width="(\d+)/) || [])[1];
    const isIcon = /0 0 (16|20|24) (16|20|24)/.test(vb) || (w && +w <= 28);
    if (!isIcon || /\$\{/.test(svg)) return svg;                 // skip diagrams + dynamic template svgs
    if (/<svg\s[^>]*\bid=/.test(svg)) return svg;                // skip JS-targeted svgs (getElementById/innerHTML) — never drop their id
    // aria: check the svg tag + ~120 chars of surrounding markup (wrapping button/a often carries the label)
    const ctx = t.slice(Math.max(0, off - 130), off + 40);
    for (const [re, cls] of ARIA) if (re.test(svg) || re.test(ctx)) { matched++; n++; return span(cls); }
    const d = (svg.match(/\bd="([^"]+)"/) || [])[1] || (svg.match(/points="([^"]+)"/) || [])[1] || '';
    const hit = PATH.find(([p]) => d.startsWith(p));
    if (hit) { matched++; n++; return span(hit[1]); }
    if (/\br="?8"?/.test(svg) && /<line\b/.test(svg) && /<circle\b/.test(svg)) { matched++; n++; return span('search'); } // magnifier
    if (/points="12 6 12 12/.test(svg)) { matched++; n++; return span('clock'); }                                          // clock face
    if (!d) { const sc = shapeClass(svg); if (sc) { matched++; n++; return span(sc); } }
    miss.set((d || 'shape').slice(0, 22), (miss.get((d || 'shape').slice(0, 22)) || 0) + 1);
    return svg;
  });
  if (APPLY && n) fs.writeFileSync(f, out, 'utf8');
  const rem = [...(out.matchAll(/<svg[\s\S]*?<\/svg>/g))].filter(m => { const vb=(m[0].match(/viewBox="([^"]*)"/)||[])[1]||''; const w=(m[0].match(/width="(\d+)/)||[])[1]; return (/0 0 (16|20|24) (16|20|24)/.test(vb)||(w&&+w<=28)) && !/\$\{/.test(m[0]); }).length;
  console.log(`${APPLY?'APPLIED':'DRY'} ${f}: convert ${n}, icon-svg left ${rem}`);
}
console.log(`\ntotal converted: ${matched}`);
if (miss.size) { console.log('UNMATCHED icon paths:'); [...miss.entries()].sort((a,b)=>b[1]-a[1]).forEach(([m,c])=>console.log(`  x${c} ${m}`)); }
