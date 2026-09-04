/* prove_fixed_chrome_budget.mjs — T113: how much of the FLOOR viewport is left for work (2026-08-26).
 *
 * 320x640 is the budget Android floor this platform targets. At that size the question is not
 * whether things fit but how much room REMAINS after the platform's own furniture: a fixed nav, a
 * hub FAB, a sticky action bar, a page-guide chip. Each is individually reasonable and they are
 * never measured together, which is exactly how a page ends up with a third of its screen spent on
 * chrome before a single row of content is drawn.
 *
 * WHAT IS MEASURED. For every visible position:fixed / position:sticky element, the probe takes the
 * UNION of the viewport rows it covers — union, not sum, because a nav and a chip that overlap cost
 * one band, and summing would invent a number nobody experiences. It reports:
 *
 *   topBand     — pixels consumed by chrome anchored at the top
 *   bottomBand  — pixels consumed by chrome anchored at the bottom
 *   coveredPct  — union coverage as a share of the 640px viewport
 *   biggest     — the single largest contributor, so a red names its cause
 *
 * ★FLOATING CHROME IS COUNTED WHERE IT SITS. A FAB pinned above the bottom edge does not free the
 * strip beneath it: content scrolling under a floating control is content a thumb cannot reliably
 * reach or read. It is counted as covered, which is what a person experiences.
 *
 * ★AND A DISMISSED CHIP IS NOT MEASURED. The probe reads what is actually on screen after load, so
 * a one-shot guide chip counts only while it is genuinely shown.
 *
 * Usage: node tools/prove_fixed_chrome_budget.mjs   (prints a per-page table + a total)
 */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const ACCT = { email: 'bryangarcia@auth.workhiveph.com', worker: 'Bryan Garcia' };
const BASELINE = 'tools/fixed_chrome_baseline.json';

// the field worker's core pages — the ones a 320 phone actually lives in
const PAGES = ['index.html', 'logbook.html', 'pm-scheduler.html', 'inventory.html',
               'dayplanner.html', 'community.html', 'hive.html', 'asset-hub.html'];

const measure = () => {
  const H = window.innerHeight, W = window.innerWidth;
  const rows = new Array(H).fill(false);
  let top = 0, bottom = 0, biggest = { what: null, px: 0 };
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' && cs.position !== 'sticky') continue;
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity || '1') < 0.05) continue;
    // ★DECORATION IS NOT CHROME. The first run of this probe reported index.html at 87.5% covered,
    // with #cursor-glow (a 440px pointer-following radial gradient) as the largest contributor -
    // and that element is pointer-events:none, z-index:0, 5% alpha, sitting BEHIND everything. The
    // aurora scene beside it is role="presentation" aria-hidden="true". Neither costs a person one
    // pixel of reach. Counting them would have banked a number nobody experiences and sent me
    // hunting a layout problem that does not exist. Chrome is what INTERCEPTS A THUMB or gets
    // ANNOUNCED: anything that takes no pointer events and is hidden from assistive tech or sits at
    // or below the content plane is background.
    if (cs.pointerEvents === 'none') {
      const z = parseInt(cs.zIndex, 10);
      const hiddenFromAT = el.getAttribute('aria-hidden') === 'true' || el.getAttribute('role') === 'presentation';
      if (hiddenFromAT || !Number.isFinite(z) || z <= 0) continue;
    }
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) continue;
    if (r.bottom <= 0 || r.top >= H) continue;
    // off to the side (a closed slide-out panel is translated out of view, not hidden)
    if (r.right <= 0 || r.left >= W) continue;
    // ★A STICKY ELEMENT TALLER THAN THE VIEWPORT IS CONTENT, NOT CHROME. The second run of this
    // probe put logbook at 50.9% and blamed a 280px `div.card` - which turned out to be the
    // "Log a Repair" FORM, `sticky top-6` and 843px tall on a 640px screen. Sticky cannot engage
    // for something taller than the viewport: it scrolls exactly like content, and nothing scrolls
    // underneath it. Counting it would have made the page's own subject look like furniture and
    // sent me deleting a panel a worker needs. Chrome PERSISTS WHILE CONTENT MOVES UNDER IT, which
    // a viewport-height element cannot do.
    if (cs.position === 'sticky' && r.height >= H) continue;
    // a full-screen overlay is a modal, not chrome - it is the content at that moment
    if (r.height >= H * 0.9 && r.width >= W * 0.9) continue;
    const a = Math.max(0, Math.floor(r.top)), b = Math.min(H, Math.ceil(r.bottom));
    for (let y = a; y < b; y++) rows[y] = true;
    const px = b - a;
    if (px > biggest.px) {
      biggest = { what: (el.id ? '#' + el.id : el.tagName.toLowerCase() + '.' + String(el.className || '').split(/\s+/)[0]).slice(0, 40), px };
    }
    if (a < H * 0.25) top = Math.max(top, b);
    if (b > H * 0.75) bottom = Math.max(bottom, H - a);
  }
  const covered = rows.filter(Boolean).length;
  return { topBand: top, bottomBand: bottom, coveredPx: covered,
           coveredPct: Math.round((covered / H) * 1000) / 10, biggest };
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 320, height: 640 }, serviceWorkers: 'block' });
const page = await ctx.newPage();

await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
await page.evaluate(async ({ email, worker, hive }) => {
  const db = (typeof getDb === 'function') ? getDb() : window.db;
  await db.auth.signInWithPassword({ email, password: 'test1234' });
  try {
    localStorage.setItem('wh_worker_name', worker);
    localStorage.setItem('wh_last_worker', worker);
    localStorage.setItem('wh_active_hive_id', hive.id);
    localStorage.setItem('wh_hive_id', hive.id);
    localStorage.setItem('wh_hive_name', hive.name);
  } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
}, { email: ACCT.email, worker: ACCT.worker, hive: HIVE });

const results = [];
for (const pg of PAGES) {
  await page.goto(`${SEEDER}/${pg}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  const m = await page.evaluate(measure);
  results.push({ page: pg, ...m });
  console.log(`  ${pg.padEnd(20)} top ${String(m.topBand).padStart(3)}px  bottom ${String(m.bottomBand).padStart(3)}px  `
    + `covered ${String(m.coveredPct).padStart(5)}%  largest: ${m.biggest.what || '-'} (${m.biggest.px}px)`);
}
await browser.close();

const worst = results.reduce((a, b) => (b.coveredPct > a.coveredPct ? b : a), results[0]);
const total = Math.round(results.reduce((s, r) => s + r.coveredPct, 0) / results.length * 10) / 10;
console.log(`\n  mean chrome coverage at 320x640: ${total}%   worst: ${worst.page} at ${worst.coveredPct}%`);

if (!existsSync(BASELINE)) {
  writeFileSync(BASELINE, JSON.stringify({ mean: total, worst: worst.coveredPct, worstPage: worst.page,
    perPage: Object.fromEntries(results.map(r => [r.page, r.coveredPct])), established: '2026-08-26' }, null, 1));
  console.log(`BASELINE established: mean ${total}%, worst ${worst.coveredPct}% (${worst.page}) — forward-only`);
  process.exit(0);
}
const base = JSON.parse(readFileSync(BASELINE, 'utf8'));
const grew = results.filter(r => r.coveredPct > (base.perPage?.[r.page] ?? 100) + 0.5);
if (grew.length) {
  console.log('FAIL fixed-chrome-budget — the platform took MORE of the floor viewport:');
  for (const g of grew) console.log(`    ${g.page}: ${base.perPage[g.page]}% -> ${g.coveredPct}% (largest: ${g.biggest.what})`);
  process.exit(1);
}
const improved = results.filter(r => r.coveredPct < (base.perPage?.[r.page] ?? 0) - 0.5);
if (improved.length) {
  base.perPage = Object.fromEntries(results.map(r => [r.page, r.coveredPct]));
  base.mean = total; base.worst = worst.coveredPct; base.worstPage = worst.page; base.ratcheted = 'auto';
  writeFileSync(BASELINE, JSON.stringify(base, null, 1));
  console.log(`PASS fixed-chrome-budget — improved on ${improved.length} page(s); ratchet lowered.`);
  process.exit(0);
}
console.log(`PASS fixed-chrome-budget — held at mean ${total}% of the 320x640 viewport.`);
process.exit(0);
