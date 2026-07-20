// Convert nav-hub.js inline-SVG icons -> centralized wh-icons.css classes.
// Config icons map by href (reliable); standalone icons (search/grid) by shape.
// Run from project root: node tools/emoji_convert_navhub.mjs
import fs from 'fs';

const FILE = 'nav-hub.js';
let t = fs.readFileSync(FILE, 'utf8');

const HREF2CLASS = {
  'index.html': 'home', 'logbook.html': 'logbook', 'inventory.html': 'parts',
  'dayplanner.html': 'calendar', 'hive.html': 'brand', 'pm-scheduler.html': 'maintenance',
  'community.html': 'community', 'analytics-report.html': 'reports', 'analytics.html': 'analytics',
  'ai-quality.html': 'ai-quality', 'assistant.html': 'ai', 'ph-intelligence.html': 'ph-intel',
  'asset-hub.html': 'asset', 'alert-hub.html': 'alert', 'audit-log.html': 'audit',
  'voice-journal.html': 'voice', 'shift-brain.html': 'brain', 'engineering-design.html': 'design',
  'project-manager.html': 'project', 'project-report.html': 'doc', 'skillmatrix.html': 'growth',
  'resume.html': 'resume', 'marketplace.html': 'cart', 'integrations.html': 'integrations',
};
const span = (name) => `<span class="ic ic-${name}" aria-hidden="true"></span>`;

// 1) config icons: replace each `icon: \`<svg>\`` using the item's own href (backward within the object)
let cfg = 0, missHref = [];
t = t.replace(/(icon:\s*`)(<svg[\s\S]*?<\/svg>)(`)/g, (full, pre, svg, post, off, str) => {
  const before = str.slice(Math.max(0, off - 340), off);
  const hrefs = before.match(/href:\s*['"]([^'"]+)['"]/g) || [];
  const href = hrefs.length ? hrefs[hrefs.length - 1].match(/href:\s*['"]([^'"]+)['"]/)[1] : '';
  const cls = HREF2CLASS[href];
  if (!cls) { missHref.push(href || '(no-href)'); return full; }
  cfg++; return pre + span(cls) + post;
});

// 2) standalone icons (search bar, apps grid) by shape
let extra = 0;
t = t.replace(/<svg[\s\S]*?<\/svg>/g, (svg) => {
  const rects = (svg.match(/<rect\b/g) || []).length;
  const lines = (svg.match(/<line\b/g) || []).length;
  if (/r="?8"?/.test(svg) && lines === 1) { extra++; return span('search'); } // magnifier
  if (rects === 4) { extra++; return span('apps'); }                          // 2x2 grid
  return svg;
});

fs.writeFileSync(FILE, t, 'utf8');
const remaining = (t.match(/<svg\b/g) || []).length;
console.log('config icons replaced (by href):', cfg);
console.log('standalone icons replaced (by shape):', extra);
console.log('remaining <svg>:', remaining);
if (missHref.length) { console.log('CONFIG ICONS WITH UNMAPPED HREF:'); [...new Set(missHref)].forEach(h => console.log('  ', h)); }
if (remaining) {
  const left = (t.match(/<svg[\s\S]*?<\/svg>/g) || []).slice(0, 6).map(s => s.replace(/\s+/g, ' ').slice(0, 70));
  console.log('SAMPLE REMAINING:'); left.forEach(s => console.log('  ', s));
}
