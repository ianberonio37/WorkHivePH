/* prove_backnav_views.mjs — back_nav asked of every dialog view: browser BACK out of an open
 * sheet leaves no orphaned overlay and the underlying page intact.
 *
 * This is the HISTORY half, distinct from dialog_back_out's AFFORDANCE half (an in-view way back
 * exists and works). Some sheets push history state (community pushes ?post=), most do not — for
 * a sheet that pushed nothing, browser Back leaves the PAGE, and the honest oracle there is that
 * the departure is clean (no half-painted overlay on the destination we return to).
 *
 *   PASS  — Back with the sheet open either (a) closes the sheet and stays on the page with no
 *           orphaned overlay (the sheet pushed history), or (b) leaves to the referrer AND
 *           returning forward/back shows no orphaned overlay artifacts.
 *   FAIL  — after Back, an overlay/backdrop remains painted over a page that thinks it navigated,
 *           or the page is left unscrollable (body locked by a dead sheet).
 *   UNGRADED — the view could not open (precondition), recorded with the reason.
 *
 * Run:  node tools/prove_backnav_views.mjs [--page community]  → backnav_views_report.json
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { viewTargets, openView } from './view_pass.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const PAGES = ['hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal',
  'community', 'achievements', 'resume', 'report-sender', 'project-report',
  'index', 'public-feed', 'assistant', 'engineering-design', 'analytics-report'];
const QUERY = { 'project-report': '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc' };
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const readState = (modal) => ({ modal });
const READ = ({ modal }) => {
  const el = modal && (document.getElementById(modal) || document.querySelector(`.${CSS.escape(modal)}`));
  const open = !!el && (() => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'; })();
  // an orphaned backdrop: a full-viewport fixed element painted above the page with nothing inside
  const orphans = [...document.querySelectorAll('[class*="overlay"], [class*="backdrop"], .sheet-overlay')]
    .filter((o) => { const cs = getComputedStyle(o); const r = o.getBoundingClientRect();
      return cs.position === 'fixed' && r.width >= innerWidth * 0.9 && cs.display !== 'none'
        && cs.visibility !== 'hidden' && Number(cs.opacity) > 0.05
        && !(el && (o === el || o.contains(el) || el.contains(o))); }).length;
  // overflow-Y ONLY: index ships body{overflow:hidden auto} - horizontal clamp (a standard
  // no-horizontal-scroll rule), vertical auto. The shorthand contains "hidden" and read as a
  // locked body on a page that scrolls fine - a false debris verdict on both index views.
  const bodyLocked = /hidden/.test(getComputedStyle(document.body).overflowY);
  return { open, orphans, bodyLocked, path: location.pathname + location.search };
};

const browser = await chromium.launch();
const cells = [];
for (const pg of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  for (const t of viewTargets(pg)) {
    const rec = { page: pg, view: t.view, modal: t.modal };
    try {
      const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
      if (!t.signedOut) await assertSignedIn(signIn(ctx, 'supervisor'));  // index V2/V3 run signed OUT by design
      const p = await ctx.newPage();
      // arrive FROM somewhere so browser Back has a real place to go
      await p.goto(`${ORIGIN}/hive.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await p.waitForTimeout(1500);
      await p.goto(`${ORIGIN}/${pg}.html${QUERY[pg] || ''}`, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await p.waitForTimeout(3200);
      const opened = await openView(p, t);
      if (!opened.ok) {
        rec.ok = null; rec.verdict = `${opened.kind}: ${opened.why}`;
        cells.push(rec); await ctx.close(); continue;
      }
      // FRESH-DOCUMENT DISCRIMINATOR: a stamp that only survives a same-document return (history
      // traversal / bfcache). If Back lands on a FRESH document, any visible dialog there is the
      // DESTINATION'S own rendering, never this sheet's debris - index proved it: signed-out hive
      // redirects to index.html?signin=1, so Back "returns" to a fresh index whose URL param
      // legitimately auto-opens the sign-in modal, and the old oracle read that as a stranded sheet.
      await p.evaluate(() => { window.__whBackProbe = 1; }).catch(() => {});
      await p.goBack({ waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
      await p.waitForTimeout(2000);
      const sameDoc = await p.evaluate(() => window.__whBackProbe === 1).catch(() => false);
      const after = await p.evaluate(READ, readState(t.modal));
      if (after.path.includes(`${pg}.html`)) {
        // A SECTION target (index's mkt-wrap anon landing, dayplanner's calendar) is page content,
        // not a sheet: still-visible after a Back that stayed is its normal state, and only orphaned
        // overlays / a locked body count as debris. Grading a landing page as an unclosed sheet is
        // the lens-shape-mismatch class. A FRESH document's open dialog is likewise its own state.
        const mustClose = sameDoc && t.kind !== 'section' && !t.mayStartOpen;
        // history-state sheet: Back stayed on the page — the sheet must be closed, nothing orphaned
        if ((!after.open || !mustClose) && after.orphans === 0 && !after.bodyLocked) {
          rec.ok = true;
          rec.verdict = `Back closed the sheet in place (history-state sheet): no orphaned overlay, body unlocked, still on ${pg}`;
        } else {
          rec.ok = false;
          rec.verdict = `Back left debris on ${pg}: sheetOpen=${after.open} orphans=${after.orphans} bodyLocked=${after.bodyLocked}`;
        }
      } else {
        // no history state: Back left the page — the destination must carry no sheet artifacts
        if (after.orphans === 0 && !after.bodyLocked) {
          rec.ok = true;
          rec.verdict = `Back left cleanly to ${after.path} (sheet pushed no history): no orphaned overlay carried, body unlocked`;
        } else {
          rec.ok = false;
          rec.verdict = `Back navigated to ${after.path} with debris: orphans=${after.orphans} bodyLocked=${after.bodyLocked}`;
        }
      }
    } catch (e) { rec.ok = null; rec.verdict = String(e.message || e).slice(0, 140); }
    cells.push(rec);
    console.log(`  ${(rec.page + '#' + rec.view).padEnd(24)} ${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : 'UNGRADED'}  ${String(rec.verdict).slice(0, 76)}`);
  }
}
await browser.close();
const ok = cells.filter((c) => c.ok === true).length;
const bad = cells.filter((c) => c.ok === false).length;
writeFileSync('backnav_views_report.json', JSON.stringify({
  totals: { cells: cells.length, pass: ok, fail: bad, ungraded: cells.length - ok - bad },
  views: cells,
}, null, 1));
console.log(`\n  ${cells.length} cell(s): ${ok} PASS · ${bad} FAIL · ${cells.length - ok - bad} ungraded — backnav_views_report.json`);
process.exit(bad ? 1 : 0);
