// Restore JS-controlled <svg id="X"> icons that the emoji converter wrongly turned into id-less spans
// (getElementById(X) then returns null -> broken). Anchor on the ~48 chars preceding the original svg
// (a unique context), find that anchor in the current file, and swap the element after it back to the
// original svg-with-id. These few stay SVG because JS drives them (toast/mic icons, a diagram's arrows).
import fs from 'fs';

const CASES = [
  ['inventory.html', 'toast-icon'],
  ['report-sender.html', 'mic-icon'],
  ['report-sender.html', 'mic-check-icon'],
  ['architecture.html', 'arrows'],
];

for (const [f, id] of CASES) {
  const orig = fs.readFileSync('.emoji_bak/' + f, 'utf8');
  let cur = fs.readFileSync(f, 'utf8');
  const re = new RegExp('<svg\\s[^>]*id="' + id + '"[\\s\\S]*?</svg>');
  const m = orig.match(re);
  if (!m) { console.log(f + ' #' + id + ': ORIGINAL NOT FOUND (skip)'); continue; }
  const svg = m[0];
  const at = orig.indexOf(svg);
  const anchor = orig.slice(Math.max(0, at - 48), at);          // unique text right before the svg

  if (cur.includes(svg)) { console.log(f + ' #' + id + ': already present (skip)'); continue; }
  const aIdx = cur.indexOf(anchor);
  if (aIdx < 0) { console.log(f + ' #' + id + ': ANCHOR NOT FOUND — needs manual fix'); continue; }
  const after = aIdx + anchor.length;
  // the element the converter left there = next <span class="ic ...></span> OR <svg ...></svg>
  const tail = cur.slice(after);
  const em = tail.match(/^\s*(<span class="ic[^>]*><\/span>|<svg\b[\s\S]*?<\/svg>)/);
  if (!em) { console.log(f + ' #' + id + ': no span/svg after anchor — manual fix'); continue; }
  cur = cur.slice(0, after) + tail.replace(em[0], em[0].match(/^\s*/)[0] + svg);
  fs.writeFileSync(f, cur, 'utf8');
  console.log(f + ' #' + id + ': RESTORED (' + em[1].slice(0, 24) + '… -> original svg)');
}
