// prove_data_honesty — the DATA HONESTY family of the live-walk wave (2026-09-06).
//
// tools/live_walk_manifest.py --family "data honesty" listed 55 rows resting on static gates: `cap is not a total`,
// `window & label agree`, `honest interpretability`, `tile == DB canonical`. Those are claims about what a NUMBER on
// the glass means, so they are answerable only where the number actually renders.
//
// Three questions, asked on the rendered page as a signed-in supervisor:
//   D1 a basis is stated     a surface that renders data carries a visible source chip (or an explicit honest-empty
//                            note). A number with no stated basis is a number nobody can check.
//   D2 window and label agree every time-window the page NAMES in a KPI label ("last 30 days") also appears in the
//                            surface's own source chip. Two windows under one roof is the platform's own bug class:
//                            a tile computed over 7 days sitting under a chip that promises 30.
//   D3 a cap is not a total   a list rendered at exactly a round row cap (20/25/50/100/200/500) must SAY it is a cap -
//                            "latest", "first", "most recent", "showing ... of". A capped list presented as the whole
//                            is the finding this platform has already fixed twice.
//
//   node tools/prove_data_honesty.mjs                       # the roster
//   node tools/prove_data_honesty.mjs --page hive.html      # one surface, verbose
//   node tools/prove_data_honesty.mjs --pages a.html,b.html
import { chromium } from 'playwright';
import { SEEDER, signIn, PAGE_QUERY, VIS_JS } from './prover_harness.mjs';

const ONLY = (() => { const i = process.argv.indexOf('--page'); return i >= 0 ? process.argv[i + 1] : null; })();
const LIST = (() => { const i = process.argv.indexOf('--pages'); return i >= 0 ? process.argv[i + 1].split(',') : null; })();
const SETTLE = (() => { const i = process.argv.indexOf('--settle'); return i >= 0 ? Number(process.argv[i + 1]) : 12000; })();

// the data-honesty family's surfaces (live_walk_manifest.py --family "data honesty", 2026-09-06)
const ROSTER = [
  'hive.html', 'logbook.html', 'inventory.html', 'asset-hub.html', 'alert-hub.html', 'analytics.html',
  'analytics-report.html', 'achievements.html', 'community.html', 'public-feed.html', 'dayplanner.html',
  'marketplace.html', 'marketplace-seller.html', 'marketplace-admin.html', 'skillmatrix.html',
  'ai-quality.html', 'agentic-rag-observability.html', 'llm-observability.html', 'platform-actions.html',
  'founder-console.html', 'plant-connections.html', 'ph-intelligence.html', 'audit-log.html',
  'symbol-gallery.html', 'validator-catalog.html', 'offline-fallback.html', 'status.html', 'shift-brain.html',
];

const AUDIT = function audit(VIS_JS) {
  const vis = (0, eval)(VIS_JS);
  const name = (e) => (e.id ? '#' + e.id : e.tagName.toLowerCase()
    + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/)[0] : ''));
  const txt = (e) => (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim();
  const out = { d1: [], d2: [], d3: [], chips: 0, lists: 0 };

  // ── D1 a stated basis ───────────────────────────────────────────────────────────────────────
  const chips = [...document.querySelectorAll('.wh-source-chip, [data-source-chip], .source-chip')].filter(vis);
  const honest = [...document.querySelectorAll('.honest-empty, .empty-state, .mod-empty, [data-wh-read-failed]')].filter(vis);
  out.chips = chips.length;
  const chipText = chips.map(txt).join(' · ').toLowerCase();
  // does this surface render DATA at all? a list/table/tile fed from the database
  const dataish = [...document.querySelectorAll('[id$="-list"], [id$="-feed"], table tbody tr, .simple-card, .kpi, [class*="kpi"]')]
    .filter(vis).length;
  if (dataish > 0 && chips.length === 0 && honest.length === 0) {
    out.d1.push(`${dataish} data element(s) render with no source chip and no honest-empty note`);
  }

  // ── D2 the windows named on the glass agree with the chip ───────────────────────────────────
  const WINDOW = /\b(last|past|previous)?\s*(\d{1,3})\s*(day|days|d|week|weeks|month|months|hour|hours|h)\b/gi;
  const norm = (n, u) => {
    const k = u.toLowerCase();
    const days = k.startsWith('d') ? +n : k.startsWith('w') ? +n * 7 : k.startsWith('m') ? +n * 30 : +n / 24;
    return Math.round(days * 10) / 10;
  };
  const chipWindows = new Set();
  let m;
  while ((m = WINDOW.exec(chipText)) !== null) chipWindows.add(norm(m[2], m[3]));
  if (chipWindows.size) {
    const labels = [...document.querySelectorAll('.sc-label, .kpi-label, .stat-label, .simple-label, h2, h3, .card-title, .section-title')]
      .filter(vis);
    for (const el of labels) {
      const t = txt(el);
      if (!t || t.length > 90) continue;
      let mm; const re = new RegExp(WINDOW.source, 'gi');
      while ((mm = re.exec(t)) !== null) {
        const w = norm(mm[2], mm[3]);
        if (!chipWindows.has(w)) {
          out.d2.push(`${name(el)} says "${mm[0].trim()}" but the source chip names ${[...chipWindows].join('/')} day(s)`);
        }
      }
    }
  }

  // ── D3 a capped list must say it is capped ──────────────────────────────────────────────────
  const CAPS = new Set([20, 25, 50, 100, 200, 250, 500]);
  const CAPWORDS = /(latest|most recent|first|showing|of\s+\d|top\s+\d|more\b|load more|page \d)/i;
  // ★A ROUND NUMBER IS NOT EVIDENCE OF A CAP (calibrated 2026-09-06). The first run flagged asset-hub for rendering
  // exactly 25 rows - which is simply how many APPROVED assets that hive has, and the page says so beside the list
  // ("25 approved assets", "4 pending · 1 rejected"). A cap is only claimable when the page ITSELF shows a larger
  // total: a short list sitting under a bigger number with nothing explaining the gap. That is the platform's own
  // bug shape, and it is what this lens must look for - not a coincidence of arithmetic.
  const totals = [...document.querySelectorAll('.simple-card, .kpi, [class*="kpi"], [id*="count"], .stat')]
    .filter(vis).flatMap((e) => (txt(e).match(/\d\d{1,6}\d/g) || []).map(Number));
  const biggest = totals.length ? Math.max(...totals) : 0;
  const containers = [...document.querySelectorAll('[id$="-list"], [id$="-feed"], [id$="-rows"], tbody, ul, ol')].filter(vis);
  for (const c of containers) {
    const kids = [...c.children].filter((k) => vis(k) && txt(k));
    if (!CAPS.has(kids.length)) continue;
    if (biggest <= kids.length) continue;   // nothing on the page claims there are more
    out.lists++;
    // look for the cap wording in the container, its heading, or the surrounding card
    const scope = c.closest('section, .card, .simple-card, .wh-card, div') || c;
    const around = (txt(scope) + ' ' + chipText).slice(0, 4000);
    if (!CAPWORDS.test(around)) {
      out.d3.push(`${name(c)} renders ${kids.length} rows while the page shows a total of ${biggest}, with no wording that says the list is capped`);
    }
  }
  for (const k of ['d1', 'd2', 'd3']) out[k] = [...new Set(out[k])].slice(0, 6);
  return out;
};

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
await signIn(ctx);

let bad = 0, n = 0;
for (const file of (ONLY ? [ONLY] : (LIST || ROSTER))) {
  n++;
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${file}${PAGE_QUERY[file] || ''}`, { waitUntil: 'load', timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(SETTLE);
  const a = await p.evaluate(AUDIT, VIS_JS).catch((e) => ({ d1: ['evaluate failed: ' + String(e).slice(0, 60)], d2: [], d3: [], chips: 0, lists: 0 }));
  const issues = [].concat(a.d1.map((s) => 'D1 no stated basis: ' + s),
                           a.d2.map((s) => 'D2 window disagreement: ' + s),
                           a.d3.map((s) => 'D3 cap shown as a total: ' + s));
  if (issues.length) bad++;
  console.log(`  ${issues.length ? 'BAD' : 'ok '} ${file.padEnd(34)} ${issues.length ? issues.length + ' issue(s)' : 'clean'} (${a.chips} chip(s), ${a.lists} capped list(s))`);
  for (const s of issues.slice(0, ONLY ? 40 : 4)) console.log(`        ${s.slice(0, 150)}`);
  await p.close();
}
await b.close();
console.log(`${bad ? 'FAIL' : 'PASS'} data-honesty - ${n - bad}/${n} surfaces state their basis, agree with their own windows, and never show a cap as a total`);
process.exit(bad ? 1 : 0);
