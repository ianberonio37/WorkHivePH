// prove_render_contract — the RENDER & CSS family of the live-walk wave (2026-09-06).
//
// tools/live_walk_manifest.py --family "render & CSS" listed 80 rows across ~40 surfaces whose evidence was a
// static gate or a board score: `render resolves` (29), `CSS contract` (19), `contrast from CSSOM` (12),
// `escHtml coverage` (11). Each of those is answerable only by LOOKING at the rendered page, and all four can be
// asked in ONE visit, which is what makes the family walkable in two runs instead of eighty.
//
// The four questions, measured on the live DOM as a signed-in supervisor:
//   R1 render resolves     no unresolved template artifact is VISIBLE - `${...}`, "undefined", "NaN",
//                          "[object Object]", "null" standing alone as text a person reads
//   R2 CSS contract        every custom property a visible element actually uses RESOLVES: no computed value
//                          still containing `var(--`, no declared token resolving to the empty string
//   R3 contrast from CSSOM composited background walked up the ancestor chain (the platform's own bug class:
//                          a translucent card over a dark page is NOT its own colour), WCAG ratio per text node
//   R4 escHtml coverage    no MARKUP is visible as text ("<div", "<span", "&lt;", "&amp;lt;") - the rendered
//                          tell of an escaping mistake in either direction
//
//   node tools/prove_render_contract.mjs                       # every surface in the roster
//   node tools/prove_render_contract.mjs --page hive.html      # one surface, verbose
//   node tools/prove_render_contract.mjs --pages a.html,b.html # a subset (the background cap)
import { chromium } from 'playwright';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();
const SETTLE = (() => { const i = process.argv.indexOf('--settle'); return i >= 0 ? Number(process.argv[i + 1]) : 9000; })();

// the render & CSS family's surfaces (live_walk_manifest.py --family "render & CSS", 2026-09-06)
const ROSTER = [
  'hive.html', 'logbook.html', 'inventory.html', 'asset-hub.html', 'dayplanner.html', 'alert-hub.html',
  'analytics.html', 'analytics-report.html', 'achievements.html', 'community.html', 'public-feed.html',
  'marketplace.html', 'marketplace-seller.html', 'marketplace-seller-profile.html', 'marketplace-admin.html',
  'assistant.html', 'shift-brain.html', 'skillmatrix.html', 'resume.html', 'report-sender.html',
  'voice-journal.html', 'integrations.html', 'plant-connections.html', 'audit-log.html', 'ai-quality.html',
  'agentic-rag-observability.html', 'llm-observability.html', 'platform-actions.html', 'founder-console.html',
  'engineering-design.html', 'pm-scheduler.html', 'project-manager.html', 'project-report.html',
  'ph-intelligence.html', 'design-system.html', 'symbol-gallery.html', 'validator-catalog.html',
  'architecture.html', 'status.html', 'index.html', 'learn/index.html',
];

const AUDIT = function audit(VIS_JS) {
  const vis = (0, eval)(VIS_JS);
  const name = (e) => (e.id ? '#' + e.id : e.tagName.toLowerCase()
    + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/)[0] : ''));
  const ownText = (e) => [...e.childNodes].filter((n) => n.nodeType === 3)
    .map((n) => n.textContent).join('').replace(/\s+/g, ' ').trim();
  const out = { r1: [], r2: [], r3: [], r4: [], sampled: 0, skipped: 0 };
  // ★A REFERENCE PAGE SHOWING CODE IS DOCUMENTATION, NOT A DEFECT (2026-09-06). design-system renders
  // `<script src="nav-hub.js">` as text on purpose - that IS the design system - and validator-catalog's rows
  // quote template syntax from the gates they catalogue. R1 (unresolved template) and R4 (markup as text) are
  // asked only OUTSIDE code samples, and never on a page that declares itself a reference catalog.
  const isRef = !!document.querySelector('meta[name="wh-page-kind"][content="reference"]');
  const inSample = (e) => !!e.closest('code, pre, samp, kbd, [class*="code"], [class*="sample"], [class*="snippet"], .ds-api, [data-code]');
  const els = [...document.querySelectorAll('body *')]
    .filter((e) => vis(e) && !e.closest('script,style,svg,template'));

  // ── R1 unresolved template artifacts a person can read ──────────────────────────────────────
  // `null`/`undefined` inside a longer sentence is prose ("undefined behaviour"); the defect is the value
  // STANDING ALONE in a slot, so the token must be the whole of that element's own text.
  const ART = /^(undefined|null|NaN|\[object Object\]|\$\{[^}]*\})$/;
  const ART_IN = /(\$\{[^}]*\}|\[object Object\])/;
  for (const e of els) {
    const t = ownText(e);
    if (!t || isRef || inSample(e)) continue;
    if (ART.test(t) || ART_IN.test(t)) out.r1.push(name(e) + ' "' + t.slice(0, 40) + '"');
  }

  // ── R2 every custom property in play resolves ───────────────────────────────────────────────
  const PROPS = ['color', 'backgroundColor', 'borderColor', 'fill'];
  for (const e of els.slice(0, 1200)) {
    const cs = getComputedStyle(e);
    for (const p of PROPS) {
      const v = cs[p];
      if (typeof v === 'string' && v.includes('var(--')) { out.r2.push(name(e) + ' ' + p + ': ' + v.slice(0, 40)); break; }
    }
  }
  // a declared token that resolves to nothing is the same defect one level up
  const root = getComputedStyle(document.documentElement);
  for (const k of ['--wh-orange', '--wh-blue', '--wh-navy', '--text', '--bg', '--border']) {
    const v = root.getPropertyValue(k);
    if (v !== '' && v.trim() === '') out.r2.push('html ' + k + ': declared but empty');
  }

  // ── R3 contrast, with the composited background walked up the chain ─────────────────────────
  const rgb = (s) => { const m = String(s).match(/rgba?\(([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?/); return m ? [ +m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4] ] : null; };
  const over = (fg, bg) => fg.slice(0, 3).map((c, i) => c * fg[3] + bg[i] * (1 - fg[3]));
  const lum = (c) => { const s = c.map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * s[0] + 0.7152 * s[1] + 0.0722 * s[2]; };
  // ★WHAT THE CSSOM CANNOT JUDGE MUST NOT BE FAILED (2026-09-06). The first run reported 1.00:1 on the primary
  // button of all 21 surfaces - an impossibly clean number, which is always the probe and not the product. Those
  // buttons paint with `linear-gradient(...)`, so their `backgroundColor` is transparent: the walk fell through to
  // the page background and compared dark navy text against dark navy. A painted background (gradient or image)
  // has no single colour to compare, so the node is SKIPPED and counted as not-computable, never failed.
  const bgOf = (el) => {
    let cur = el, acc = null;
    while (cur && cur !== document.documentElement) {
      const cs = getComputedStyle(cur);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null;   // painted: not computable
      const c = rgb(cs.backgroundColor);
      if (c && c[3] > 0) { acc = acc ? over(acc.concat(1), c) : c.slice(0, 3).map((v, i) => v * c[3] + (255 * 0) * (1 - c[3]));
                           if (c[3] >= 0.999) return acc; }
      cur = cur.parentElement;
    }
    const page = rgb(getComputedStyle(document.body).backgroundColor) || [11, 15, 26, 1];
    return acc || page.slice(0, 3);
  };
  const texts = els.filter((e) => ownText(e).length > 2);
  out.sampled = texts.length;
  for (const e of texts.slice(0, 400)) {
    const cs = getComputedStyle(e);
    const fg = rgb(cs.color); if (!fg) continue;
    const bg = bgOf(e);
    if (!bg) { out.skipped = (out.skipped || 0) + 1; continue; }   // painted background: say so, do not guess
    const f = fg[3] < 1 ? over(fg, bg) : fg.slice(0, 3);
    const L1 = lum(f), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const px = parseFloat(cs.fontSize) || 16;
    const bold = (parseInt(cs.fontWeight) || 400) >= 700;
    const floor = (px >= 24 || (px >= 18.66 && bold)) ? 3.0 : 4.5;
    if (ratio + 0.05 < floor) out.r3.push(name(e) + ' ' + ratio.toFixed(2) + ':1 < ' + floor + ' @' + Math.round(px) + 'px "' + ownText(e).slice(0, 26) + '"');
  }

  // ── R4 markup visible as text ───────────────────────────────────────────────────────────────
  const MARK = /(<\/?(div|span|p|b|i|script|img|a)\b|&lt;|&amp;(lt|gt|amp);|&gt;)/i;
  for (const e of els) {
    const t = ownText(e);
    if (!t || isRef || inSample(e)) continue;
    if (MARK.test(t)) out.r4.push(name(e) + ' "' + t.slice(0, 44) + '"');
  }
  for (const k of ['r1', 'r2', 'r3', 'r4']) out[k] = [...new Set(out[k])].slice(0, 6);
  return out;
};

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
await signIn(ctx);

let bad = 0, n = 0;
for (const file of (ONLY ? [ONLY] : (LIST || ROSTER))) {
  n++;
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', (e) => errs.push(String(e).slice(0, 90)));
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE);
  const a = await p.evaluate(AUDIT, VIS_JS).catch((e) => ({ r1: ['evaluate failed: ' + String(e).slice(0, 60)], r2: [], r3: [], r4: [], sampled: 0 }));
  const issues = [].concat(
    a.r1.map((s) => 'R1 unresolved: ' + s),
    a.r2.map((s) => 'R2 var unresolved: ' + s),
    a.r3.map((s) => 'R3 contrast: ' + s),
    a.r4.map((s) => 'R4 markup as text: ' + s),
    errs.length ? ['page error: ' + errs[0]] : []);
  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(34)} ${issues.length ? issues.length + ' issue(s)' : 'clean'} (${a.sampled} text nodes, ${a.skipped || 0} on painted backgrounds)`);
  for (const s of issues.slice(0, ONLY ? 40 : 5)) console.log(`        ${s.slice(0, 150)}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} render-contract - ${n - bad}/${n} surfaces resolve their templates and tokens, meet contrast, and show no markup as text`);
process.exit(bad ? 1 : 0);
