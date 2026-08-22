// prove_back_nav.mjs — the CG `back_nav` oracle, measured with the real browser Back button.
//
// THE ORACLE: "browser Back out of a sheet leaves no orphaned overlay and no write half-applied; the
// underlying list reflects what actually happened."
//
// ★THIS IS NOT `back_out`, AND THE DIFFERENCE IS THE WHOLE POINT. prove_back_out.mjs and
// prove_dialog_back_out.mjs measure the page's OWN back affordance (`.wf-back`, `.back-link`) — a control
// the product ships and controls. This measures the one control the product does NOT own: the browser's
// Back button, which a person on a phone reaches for by reflex with a sheet open. Nothing about a
// working `.wf-back` predicts what Back does, so these rows stayed owed while the others went green.
//
// ★BACK NEEDS SOMEWHERE TO GO, so the walk navigates from a REFERRER first. A `goto()` straight to the
// page leaves exactly one history entry, `goBack()` is then a no-op, and the prover would report that
// every page "stayed put with no orphan" — a green earned by never testing anything. The referrer is a
// real page in the app, so Back has a genuine destination and the two outcomes are distinguishable.
//
// ★THE FOUR SHAPES, and only two of them are defects:
//   · CLOSED   — Back dismissed the sheet and stayed on the page. The sheet pushed a history entry; this
//                is what a person expects and it is the best outcome.
//   · LEFT     — Back navigated to the referrer, sheet and all. The place is lost, but there is no
//                orphaned overlay and no half-applied write, so the ORACLE is satisfied. Recorded as the
//                weaker guarantee it is rather than failed — the same tier-1/tier-2 honesty
//                prove_dialog_back_out.mjs already applies to the in-page affordance.
//   · ORPHANED — an overlay is still on screen after Back. This is the defect the oracle names: the
//                person is stranded on a page they navigated away from, behind a sheet they cannot see
//                past. FAIL.
//   · CHANGED  — the underlying list is not what it was before the sheet opened. FAIL.
//
// ★NON-WRITING BY CONSTRUCTION. The walk opens a sheet and presses Back. Nothing is typed, nothing is
// submitted, no mutating request is issued — so "no write half-applied" is asserted by comparing the
// underlying list to itself, and any difference is a genuine side effect of opening and dismissing.
//
// ★THE ZERO-DENOMINATOR RAIL. A target whose sheet never opened was not tested: pressing Back with no
// sheet on screen measures nothing at all, and banking that as a pass is how coverage improves by
// deleting obligations. Those return UNGRADED with the reason.
//
// USAGE:  node tools/prove_back_nav.mjs [--page <name>]
// OUTPUT: back_nav_report.json

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { TARGETS } from './dialog_targets.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const QUERY = { 'project-report': '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc' };
// A referrer that is neither the page under test nor a page that would redirect: a plain, always-present
// surface. Back from the page must land HERE when the sheet does not push its own history entry.
const REFERRER = '/workhive/index.html';

// What is on screen, and what the page's main list holds. Both are read the same way before and after,
// so the comparison is like-for-like.
// ★THE REGISTRY NAMES THE SHEET, SO ASK IT DIRECTLY. My first version detected "an overlay" by area —
// any fixed block covering >12% of the viewport — and 18 of 33 targets came back "no overlay appeared",
// while prove_modal_escape_live.mjs opens those same sheets without trouble. A heuristic stand-in for a
// fact I already had in dialog_targets.mjs turned working pages into unmeasurable ones.
// ★AND THE UNDERLYING LIST MUST EXCLUDE THE SHEET'S OWN ROWS. Counting every row-like node in the
// document — hidden ones included — meant that opening a sheet which RENDERS rows (resume's review
// sheet injects the extracted items; community's composer adds its own) permanently inflated the count,
// and a dismissed-but-still-in-DOM sheet then read as "the underlying list changed": 18->21 and 47->48,
// two defects manufactured by counting the thing under test. The list is the VISIBLE rows OUTSIDE any
// overlay.
const snapshot = (modalSel) => {
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 4 && r.height > 4 && cs.display !== 'none' && cs.visibility !== 'hidden'
      && Number(cs.opacity) > 0.05;
  };
  // An overlay is anything the page itself treats as a sheet: a dialog role, or a fixed-position block
  // that covers a meaningful part of the viewport. Both forms exist on this platform.
  const overlays = [...document.querySelectorAll(
    '[role="dialog"], .modal, .overlay, .sheet, [class*="modal"], [class*="overlay"], [class*="sheet"]')]
    .filter((el) => {
      if (!vis(el)) return false;
      const r = el.getBoundingClientRect();
      return r.width * r.height > 0.12 * window.innerWidth * window.innerHeight;
    })
    .map((el) => (el.id ? '#' + el.id : el.tagName + '.' + String(el.className).slice(0, 40)));
  // The underlying list: the count of row-like elements the page renders. Not WHICH rows — a realtime
  // feed may legitimately gain one mid-walk — but a structural count that a half-applied write moves.
  const OVER = '[role="dialog"], .modal, .overlay, .sheet, [class*="modal"], [class*="overlay"], '
    + '[class*="sheet"]';
  const rows = [...document.querySelectorAll(
    'tr, li, .card, [class*="-row"], [class*="-card"], [data-id], [data-post-id]')]
    .filter((el) => vis(el) && !el.closest(OVER)).length;
  // The sheet this target is about, by the selector the registry records for it.
  let sheet = null;
  if (modalSel) {
    const el = document.getElementById(modalSel) || document.querySelector('.' + modalSel)
      || document.querySelector('[data-modal="' + modalSel + '"]');
    sheet = el ? vis(el) : null;
  }
  return { overlays, rows, sheet, url: location.pathname + location.search };
};

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const out = { origin: ORIGIN, referrer: REFERRER, targets: [] };

  const list = TARGETS.filter((t) => !t.signedOut && !t.unreachable && !t.notDrivable
    && (!ONE || t.page === ONE));

  for (const t of list) {
    const rec = { page: t.page, view: t.view, modal: t.modal };
    const page = await ctx.newPage();
    try {
      // 1. A real history entry to go back TO.
      await page.goto(ORIGIN + REFERRER, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(1500);
      await page.goto(ORIGIN + '/workhive/' + t.page + '.html' + (QUERY[t.page] || ''),
        { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(6000);

      // 2. The state BEFORE the sheet — the thing Back must return the person to.
      const before = await page.evaluate(snapshot, t.modal);

      // 3. Reach the state that reveals the opener, if the target needs one. A failed precondition is a
      //    fact about the page, never a defect of this oracle.
      if (t.pre) {
        const preOk = await page.evaluate((src) => {
          try { eval(src); return true; } catch (e) { return String(e.message || e); }
        }, t.pre);
        if (preOk !== true) {
          rec.ok = null; rec.why = 'precondition did not hold, so the sheet was never reachable: ' + preOk;
          out.targets.push(rec); await page.close(); continue;
        }
        await page.waitForTimeout(1800);
      }

      // 4. Open the sheet by the path dialog_targets.mjs records for it.
      if (t.openBy === 'click') {
        const shown = await page.evaluate((sel) => {
          const el = document.querySelector(sel);
          if (!el) return 'absent';
          const r = el.getBoundingClientRect();
          if (r.width < 1 || r.height < 1) return 'not visible';
          el.click(); return true;
        }, t.opener).catch((e) => String(e.message || e));
        if (shown !== true) {
          rec.ok = null; rec.why = 'opener ' + t.opener + ' was ' + shown + ', so no sheet opened';
          out.targets.push(rec); await page.close(); continue;
        }
      } else {
        await page.evaluate((src) => eval(src), t.fn).catch(() => {});
      }
      await page.waitForTimeout(1600);

      const open = await page.evaluate(snapshot, t.modal);
      // ★A SHEET THAT NEVER OPENED CANNOT TEST BACK. Pressing Back against an unchanged page measures
      // the navigation, not the oracle — UNGRADED rather than a pass over nothing.
      const opened = open.sheet === true
        || open.overlays.length > before.overlays.length
        || open.overlays.some((o) => !before.overlays.includes(o));
      if (!opened) {
        rec.ok = null;
        rec.why = 'no overlay appeared after the open path ran, so there was no sheet to press Back out '
          + 'of; UNGRADED rather than a pass over an empty set';
        out.targets.push(rec); await page.close(); continue;
      }
      rec.overlayOnOpen = open.overlays.slice(0, 3);

      // 5. The browser's own Back.
      await page.goBack({ waitUntil: 'domcontentloaded', timeout: 20000 }).catch(() => {});
      await page.waitForTimeout(2500);
      const after = await page.evaluate(snapshot, t.modal);

      const leftPage = !after.url.includes(t.page + '.html');
      const stillOpen = after.sheet === true
        || (after.sheet === null && after.overlays.some((o) => open.overlays.includes(o)));
      // Only meaningful when we are still on the page — the referrer has its own, different row count.
      const rowsMoved = !leftPage && Math.abs(after.rows - before.rows) > 0;

      rec.shape = stillOpen ? 'ORPHANED' : leftPage ? 'LEFT' : 'CLOSED';
      rec.rows = { before: before.rows, after: after.rows };
      rec.url = after.url;
      rec.ok = !stillOpen && !rowsMoved;
      rec.why = stillOpen
        ? 'Back ran and the sheet is STILL on screen (' + after.overlays.slice(0, 2).join(', ')
          + ') - the person is behind an overlay on a page they navigated away from'
        : rowsMoved
          ? 'the underlying list changed across an open-and-Back that wrote nothing: '
            + before.rows + ' -> ' + after.rows + ' rows'
          : leftPage
            ? 'Back left the page for the referrer rather than dismissing the sheet: no orphaned overlay '
              + 'and no half-applied write, so the oracle holds, but the sheet pushed no history entry '
              + 'and the person loses their place'
            : 'Back dismissed the sheet and stayed on the page, with the underlying list unchanged ('
              + before.rows + ' rows before and after)';
    } catch (e) {
      rec.ok = null; rec.why = 'could not measure: ' + String(e.message || e).slice(0, 120);
    }
    await page.close();
    out.targets.push(rec);
    console.log('  ' + (rec.ok === null ? 'UNGRADED' : rec.ok ? 'PASS    ' : 'FAIL    ')
      + ' ' + (t.page + ' ' + t.view).padEnd(26) + ' ' + (rec.shape || '').padEnd(9)
      + ' ' + (rec.why || '').slice(0, 74));
  }
  await browser.close();
  writeFileSync(path.join(ROOT, 'back_nav_report.json'), JSON.stringify(out, null, 1));
  const g = out.targets.filter((t) => t.ok !== null);
  // gate promotion 2026-08-21: failing rows set the exit code.
  if (process.argv.includes('--gate')) process.exitCode = g.filter((t) => !t.ok).length ? 1 : 0;
  const shapes = g.reduce((a, t) => { a[t.shape] = (a[t.shape] || 0) + 1; return a; }, {});
  console.log('\n  ' + g.filter((t) => t.ok).length + ' pass | ' + g.filter((t) => !t.ok).length
    + ' fail | ' + (out.targets.length - g.length) + ' ungraded   shapes: ' + JSON.stringify(shapes));
};
run().catch((e) => { console.error(e); process.exit(1); });
