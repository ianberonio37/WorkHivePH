// prove_audit_visible_rect.mjs - TEETH for the phone_fit_audit occlusion visible-rect fix (Wave 4, 2026-09-14).
//
// The wave-4 nav-hub ratchet flagged the LAST search-result row of the global-search overlay as "covered by
// #wh-search-overlay" (W41438/W41390): the row was scrolled partway out of its scroll container, so its GEOMETRIC
// centre fell in the clipped band where elementFromPoint returned the overlay chrome, not the row. The fix: the
// occlusion probe now tests the centre of the control's VISIBLE (clip-intersected) rect, not its raw centre. A gate
// (or a fix) that cannot be shown to bite is a no-op, so this asks the audit to be RIGHT on two synthetic pages
// whose truth is known:
//
//   scrolled-out - a scrolling list whose last row is half-cut at the container's bottom, with a sibling footer
//                  painting over the row's raw centre -> the audit MUST NOT report the row as occluded (the fix)
//   covered      - a plain button with a position:fixed bar sitting ON it -> the audit MUST still report occlusion
//                  (the fix must not blind the real case it exists to catch)
//
//   node tools/prove_audit_visible_rect.mjs
import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';

const AUDIT = readFileSync('tools/phone_fit_audit.browser.js', 'utf8');   // installs window.__W4_AUDIT
const HEAD = '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width"><style>body{margin:0;font-family:sans-serif}</style></head><body>';

// A scroll container of 60px rows at page y 0-200; a footer sibling DIRECTLY BELOW it at y 200-232 (no overlap of
// the container's visible area). We scroll so a row's top sits at container-y 175: it is visible 175-200 (25px) and
// CLIPPED below 200, but its raw geometric centre (≈205) falls in the footer's band. The row's VISIBLE part is not
// covered by anything; only its clipped (unpainted) half sits "under" the footer. Old code probed the raw centre
// (205 -> footer -> false "covered"); the fix probes the visible centre (≈187 -> the row -> no finding).
const SCROLLED_OUT = HEAD
  + '<main style="padding:0">'
  + '<div id="results" style="height:200px;overflow:auto;position:relative">'
  + Array.from({ length: 9 }, (_, i) =>
      `<a class="ws-row" href="#r${i}" style="display:block;height:60px;line-height:60px;background:${i % 2 ? '#eee' : '#f7f7f7'}">Row ${i}</a>`).join('')
  + '</div>'
  + '<div id="footer" style="height:32px;background:#222;color:#fff">footer below the list</div>'
  + '</main></body></html>';

const COVERED = HEAD
  + '<main style="padding:16px 16px 120px"><h1>Covered control</h1>'
  + '<p><button id="save" style="height:40px;width:120px">Save</button></p></main>'
  + '<div id="bar" style="position:fixed;left:0;right:0;top:0;height:120px;background:#e33;z-index:1000">fixed bar over Save</div>'
  + '</body></html>';

async function auditOf(page, html, prep) {
  await page.setContent(html, { waitUntil: 'load' });
  await page.addScriptTag({ content: AUDIT });
  if (prep) await page.evaluate(prep);
  return page.evaluate(() => window.__W4_AUDIT(null, { step: 'synthetic' }));
}

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
const fails = [];

// scroll the list so the last row is half-cut at the container's visible bottom
const out = await auditOf(page, SCROLLED_OUT, () => { const r = document.getElementById('results'); r.scrollTop = 5 * 60 - 175; });
const rowFlag = (out.occlusion || []).find((s) => /ws-row/.test(s));
if (rowFlag) fails.push(`a scrolled-out row must NOT read as occluded (visible-rect fix) - got "${rowFlag.slice(0, 120)}"`);

const cov = await auditOf(page, COVERED);
const saveFlag = (cov.occlusion || []).find((s) => /save/i.test(s) && /bar/i.test(s));
if (!saveFlag) fails.push(`a button under a fixed bar MUST read as occluded (no regression) - occlusion=${JSON.stringify((cov.occlusion || []).slice(0, 3))}`);

await b.close();
if (fails.length) {
  console.log('FAIL audit-visible-rect - ' + fails.join(' | '));
  process.exit(1);
}
console.log(`PASS audit-visible-rect - a row scrolled into its clip band no longer false-flags (0 ws-row occlusion), and a button under a fixed bar still bites ("${saveFlag.slice(0, 70)}")`);
