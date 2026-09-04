/* prove_width_utilisation.mjs — T114 + T115: the widths between phone and desk (2026-08-26).
 *
 * TWO OPEN ITEMS, ONE MEASUREMENT. T114 asks whether 768 — the awkward middle nobody designs for —
 * is coherent. T115 recorded a specific nit at 1920: line lengths of 104-131ch, well past the
 * 45-90ch that reading research puts a comfortable measure at, and asked whether the width is USED
 * or merely stretched. Both are answered by the same two numbers per page:
 *
 *   fill%   — how much of the viewport the main content actually occupies. Very low means the page
 *             renders a phone layout on a monitor; very high at 1920 usually means text running the
 *             full width, which is the line-length problem wearing a different hat.
 *   maxCh   — the longest visible line of prose, in characters, measured from the RENDERED text and
 *             its OWN font metrics rather than guessed from a max-width.
 *
 * ★CH IS MEASURED, NOT ASSUMED. A "ch" is the width of the digit zero in the element's own font, so
 * a line's character measure depends on the font actually applied to it — not on a stylesheet's
 * intent. The probe reads each block's computed font and asks the browser to measure it.
 *
 * ★AND ONLY PROSE COUNTS. A 200-character table row or a code block is not a reading measure and
 * capping it would be wrong; the probe looks at block elements whose text is a sentence (spaces,
 * length, no tabular ancestor).
 *
 * Forward-only per page+width: line length may shrink, never grow.
 *
 * Usage: node tools/prove_width_utilisation.mjs
 */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';

const SEEDER = process.env.WH_SEEDER || 'http://127.0.0.1:5000';
const HIVE = { id: '084c113b-99c0-45c6-a8e8-b4b8349da46d', name: 'Baguio Textile Mills' };
const BASELINE = 'tools/width_utilisation_baseline.json';
const WIDTHS = [768, 1920];
const PAGES = ['index.html', 'analytics.html', 'logbook.html', 'hive.html', 'pm-scheduler.html'];

const measure = () => {
  const W = window.innerWidth;
  // fill: the widest visible top-level content block, as a share of the viewport
  let widest = 0;
  const main = document.querySelector('main') || document.body;
  for (const el of main.children) {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) widest = Math.max(widest, r.width);
  }
  // maxCh: the longest line of PROSE, in that element's own character width
  const cv = document.createElement('canvas').getContext('2d');
  let maxCh = 0, worst = null;
  for (const el of document.querySelectorAll('p, li, .card p, blockquote')) {
    const r = el.getBoundingClientRect();
    if (r.width < 40 || r.height < 8) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (el.closest('table, pre, code, [class*="table"]')) continue;   // not a reading measure
    const txt = (el.innerText || '').trim();
    if (txt.length < 60 || (txt.match(/\s/g) || []).length < 8) continue;   // not prose
    // ★A SOURCE CHIP IS NOT PROSE, and the first run of this probe reported 175ch "prose lines" that
    // were all of them: "Live . refreshed on load . Based on ..." and "Saved snapshot, computed 5h
    // ago . ...". Those are the platform's freshness/source chips - dense metadata SCANNED in one
    // glance, not read left-to-right for comprehension - and capping them at a reading measure would
    // WRAP them, making a one-line label into three. A measure that admits them would ratchet the
    // wrong number and invite exactly the wrong fix. The chip idiom here is middot-separated.
    if ((txt.match(/·/g) || []).length >= 2) continue;
    cv.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const zero = cv.measureText('0').width || parseFloat(cs.fontSize) * 0.5;
    const ch = Math.round(r.width / zero);
    if (ch > maxCh) { maxCh = ch; worst = txt.slice(0, 34); }
  }
  return { fill: Math.round((widest / W) * 1000) / 10, maxCh, worst };
};

const browser = await chromium.launch();
const results = [];
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: 'block' });
  const page = await ctx.newPage();
  await page.goto(`${SEEDER}/shift-brain.html`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => !!(window.supabase && typeof window.supabase.createClient === 'function'), { timeout: 25000 });
  await page.evaluate(async ({ hive }) => {
    const db = (typeof getDb === 'function') ? getDb() : window.db;
    await db.auth.signInWithPassword({ email: 'leandromarquez@auth.workhiveph.com', password: 'test1234' });
    try {
      localStorage.setItem('wh_worker_name', 'Leandro Marquez');
      localStorage.setItem('wh_last_worker', 'Leandro Marquez');
      localStorage.setItem('wh_active_hive_id', hive.id);
      localStorage.setItem('wh_hive_id', hive.id);
      localStorage.setItem('wh_hive_name', hive.name);
      localStorage.setItem('wh_hive_role', 'supervisor');
    } catch (_) { /* empty-catch-allow: identity seeding is best-effort */ }
  }, { hive: HIVE });

  for (const pg of PAGES) {
    for (const w of WIDTHS) {
      await page.setViewportSize({ width: w, height: 900 });
      await page.goto(`${SEEDER}/${pg}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(4500);
      // ★MEASURE THE PAGE YOU NAMED, OR MEASURE NOTHING (2026-08-28). Every gated page here calls
      // whSignInWall() without a session, so a run whose sign-in silently failed lands on
      // index.html for EVERY entry - and this loop happily measured it and labelled the numbers
      // `analytics.html`, `pm-scheduler.html`, `hive.html`. That is exactly what happened: one run
      // reported all five pages with byte-identical values (99.2% fill, 73ch "Build a verified
      // reputation in the") because all five WERE index.html, and the ratchet then reported prose
      // "regressions" on pages the browser never opened. A wrong number is recoverable; a wrong
      // number wearing the right page's name sends someone to edit a file that is fine.
      const landed = new URL(page.url()).pathname.split('/').pop() || 'index.html';
      if (landed !== pg) {
        console.log(`  ABORT: asked for ${pg} and landed on ${landed} - the session is not signed `
          + `in, so every page would measure the sign-in wall. Refusing to attribute one page's `
          + `prose to another.`);
        process.exit(1);
      }
      const m = await page.evaluate(measure);
      results.push({ key: `${pg}@${w}`, ...m });
      console.log(`  ${pg.padEnd(20)} @${w}  fill ${String(m.fill).padStart(5)}%  longest prose line ${String(m.maxCh).padStart(4)}ch`
        + (m.worst ? `  "${m.worst}"` : ''));
    }
  }
} finally {
  await browser.close();
}

if (!results.length) { console.log('FAIL width-utilisation — NOTHING WAS MEASURED.'); process.exit(1); }
const now = Object.fromEntries(results.map((r) => [r.key, r.maxCh]));
if (!existsSync(BASELINE)) {
  writeFileSync(BASELINE, JSON.stringify({ maxCh: now, established: '2026-08-26' }, null, 1));
  console.log(`BASELINE established — forward-only on longest prose line per page+width`);
  process.exit(0);
}
const base = JSON.parse(readFileSync(BASELINE, 'utf8'));
const grew = results.filter((r) => r.maxCh > (base.maxCh?.[r.key] ?? 999) + 2);
if (grew.length) {
  console.log('FAIL width-utilisation — prose lines got LONGER:');
  for (const g of grew) console.log(`    ${g.key}: ${base.maxCh[g.key]}ch -> ${g.maxCh}ch  "${g.worst}"`);
  process.exit(1);
}
const improved = results.filter((r) => r.maxCh < (base.maxCh?.[r.key] ?? 0) - 2);
if (improved.length) {
  base.maxCh = now; base.ratcheted = 'auto';
  writeFileSync(BASELINE, JSON.stringify(base, null, 1));
  console.log(`PASS width-utilisation — shorter on ${improved.length} page/width pair(s); ratchet lowered.`);
  process.exit(0);
}
console.log('PASS width-utilisation — no prose line got longer at any measured width.');
process.exit(0);
