// prove_modal_escape_live.mjs — half TWO of CO `back_out` for the V2/V3 dialog views: the BEHAVIOUR.
//
// Half one (prove_modal_escape_adoption.mjs) proved from source that all 15 dialog views have SOME
// keyboard way out — 10 through the shared `whModalA11y` helper, 5 hand-rolled. Adoption is not
// behaviour, and the helper's behaviour had only ever been driven on ONE marketplace sheet, so nothing
// was banked off that. This file drives the modals themselves.
//
// EVERY TARGET BELOW CARRIES THE SOURCE REF THAT ESTABLISHED ITS OPEN PATH. None was found by matching a
// label: the roadmap records a generic opener regex matching "Load more posts" instead of a composer, and
// a mechanical sweep resolved only 4 of 15 openers, so the rest were READ. A target with a guessed
// selector would silently drive the wrong control and report a confident non-result.
//
// TWO ASSERTIONS, AND THEY ARE DELIBERATELY NOT THE SAME STRENGTH:
//   1. ESCAPE CLOSES — provable for every target here.
//   2. FOCUS RETURNS TO THE OPENER — provable ONLY where a real opener ELEMENT is clicked. `whModalA11y`
//      restores focus to whatever `document.activeElement` was when the modal opened; open one by
//      calling the page's function directly and that is `<body>`, so a focus-restore assertion would be
//      measuring the probe's own starting state. Where the open path is a function call, focus-restore is
//      recorded as `not-assertable-by-this-path` rather than passed. A green that cannot fail is not a green.
//
// NON-WRITING: it opens a dialog and presses Escape. It types nothing and submits nothing.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { TARGETS } from './dialog_targets.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// The target table now lives in tools/dialog_targets.mjs, shared with the dialog-layout prover so the
// two cannot drift apart — the same reason the PARENT map in prove_back_out.mjs is checked against
// wayfinding.js on every run.


const VISIBLE = (id) => {
  const el = document.getElementById(id);
  if (!el) return { present: false };
  const s = getComputedStyle(el); const b = el.getBoundingClientRect();
  return { present: true,
           visible: s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.01
                    && b.width > 0 && b.height > 0,
           display: s.display, hidden: el.classList.contains('hidden'),
           h: Math.round(b.height) };
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await assertSignedIn(signIn(ctx, 'supervisor'));
const pageSignedIn = await ctx.newPage();
// A SIGNED-OUT context, created lazily, for dialogs that only exist for a signed-out visitor. index's
// #signin-modal is the case: openSignIn() checks whWorker() first and, for a signed-in caller, opens the
// USER MENU and returns without ever showing the modal (index.html:2917). Driving it from the signed-in
// context would have reported "did not become visible" — a fact about the persona, not the dialog.
let anonCtx = null, anonPage = null;

const results = [];
for (const t of TARGETS.filter((x) => !ONE || x.page === ONE.replace(/\.html$/, ''))) {
  const rec = { ...t };
  let page = pageSignedIn;
  // A TAB PANEL IS NOT A DIALOG AND MUST NOT BE ASKED TO CLOSE ON ESCAPE. Escape closing a tab view would
  // be a defect, not a pass — the way out of a tab is the page-level back affordance, which the V1
  // `back_out` row measures against wayfinding.js's own contract. Recorded here as out-of-scope-for-this-
  // prover rather than omitted, so the target list stays one shared table and the denominator stays honest.
  if (t.kind === 'tab' || t.kind === 'section') {
    rec.ok = null;
    rec.error = `${t.kind} view, not a dialog — Escape is not its exit; the page-level back affordance is, `
      + 'and that is measured by the V1 back_out row';
    results.push(rec);
    console.log(`  ${t.page.padEnd(14)} ${t.view} #${t.modal.padEnd(17)} n/a       ${t.kind} view — `
      + 'Escape is not its exit');
    continue;
  }
  if (t.notDrivable) {
    rec.ok = null;
    rec.error = `NOT DRIVABLE by a read-only probe: ${t.notDrivable}`;
    results.push(rec);
    console.log(`  ${t.page.padEnd(14)} ${t.view} #${t.modal.padEnd(17)} UNGRADED  `
      + `not drivable read-only — ${String(t.notDrivable).slice(0, 60)}`);
    continue;
  }
  try {
    if (t.signedOut) {
      if (!anonCtx) {
        anonCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });
        anonPage = await anonCtx.newPage();
      }
      page = anonPage;
    }
    await page.goto(`${ORIGIN}/${t.page}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(3000);
    const landed = (page.url().split('/').pop() || '').replace(/\.html.*$/, '');
    if (landed !== t.page) { rec.error = `landed on ${landed}, not the page under test`; }
    else {
      // PRECONDITION, run before anything is measured. Its failure is UNGRADED, never a modal defect —
      // "no assets in this hive" says nothing about whether Escape works.
      if (t.pre) {
        rec.preResult = await page.evaluate((code) => {
          try { eval(code); return 'ok'; } catch (e) { return 'threw: ' + String(e.message || e).slice(0, 90); }
        }, t.pre);
        await page.waitForTimeout(1500);
        if (String(rec.preResult).startsWith('threw')) {
          rec.error = `precondition ${rec.preResult} — cannot reach the state that reveals the opener`;
        }
      }
      rec.before = rec.error ? null : await page.evaluate(VISIBLE, t.modal);
      if (rec.error) { /* precondition already failed — fall through to the UNGRADED path */ }
      else if (!rec.before.present) {
        rec.error = `#${t.modal} is not in the DOM — the anatomy ref may be stale`;
      } else if (rec.before.visible && !t.mayStartOpen) {
        rec.error = `#${t.modal} is ALREADY visible before opening — cannot prove Escape closed it`;
      } else if (rec.before.visible && t.mayStartOpen) {
        // A DIALOG THAT THE PAGE ITSELF OPENS ON LOAD. hive's #intent-capture is a first-run prompt that
        // is already up when the page settles, so there is no open step to drive — and refusing the whole
        // target for that reason would drop a dialog a person genuinely has to escape from. Escape-closes
        // is still exactly as provable; what is NOT claimed here is that any open path works, and
        // focus-restore is not assertable because nothing was clicked to open it.
        rec.startedOpen = true;
        rec.opened = rec.before;
        await page.keyboard.press('Escape');
        await page.waitForTimeout(900);
        rec.afterEscape = await page.evaluate(VISIBLE, t.modal);
        rec.escapeClosed = !rec.afterEscape.visible;
        rec.focusAfter = await page.evaluate(() => {
          const a = document.activeElement; return a ? (a.id ? '#' + a.id : a.tagName) : null;
        });
        rec.focusRestored = null;
        rec.ok = rec.escapeClosed;
      } else {
        // OPEN
        if (t.openBy === 'click') {
          const box = await page.evaluate((sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const b = el.getBoundingClientRect(); const s = getComputedStyle(el);
            return { w: Math.round(b.width), h: Math.round(b.height),
                     shown: s.display !== 'none' && s.visibility !== 'hidden' && b.height > 0 };
          }, t.opener);
          rec.openerBox = box;
          // A PROGRAMMATIC CLICK ON AN UNREACHABLE CONTROL PROVES NOTHING — assert a real box first.
          if (!box || !box.shown) {
            // An opener that is not visible is normally UNGRADED — it is usually a data or persona state
            // ("this hive has no PM assets"), which says nothing about the dialog. But where the target
            // carries a VERIFIED source fact explaining that the control can never be reached, that is a
            // finding about the product, not a gap in the probe, and it must not hide behind a skip.
            if (t.unreachable) { rec.ok = false; rec.unreachable = t.unreachable; }
            else rec.error = `opener ${t.opener} is absent or not visible`;
          }
          else {
            await page.click(t.opener, { timeout: 4000 });
            await page.waitForTimeout(900);
          }
        } else {
          rec.fnResult = await page.evaluate((code) => {
            try { /* eslint-disable no-eval */ eval(code); return 'called'; }
            catch (e) { return 'threw: ' + String(e).slice(0, 90); }
          }, t.fn);
          if (String(rec.fnResult).startsWith('threw')) rec.error = `opener fn ${rec.fnResult}`;
          await page.waitForTimeout(900);
        }

        // `rec.unreachable` is already a settled FAILING verdict — falling through would overwrite it
        // with "did not become visible", which is true but describes the symptom instead of the cause.
        if (!rec.error && !rec.unreachable) {
          rec.opened = await page.evaluate(VISIBLE, t.modal);
          rec.focusedAtOpen = await page.evaluate(() => {
            const a = document.activeElement;
            return a ? (a.id ? '#' + a.id : a.tagName) : null;
          });
          if (!rec.opened.visible) {
            rec.error = `#${t.modal} did not become visible after the open path ran `
              + `(display=${rec.opened.display}, hidden=${rec.opened.hidden})`;
          } else {
            // ESCAPE
            await page.keyboard.press('Escape');
            await page.waitForTimeout(900);
            rec.afterEscape = await page.evaluate(VISIBLE, t.modal);
            rec.escapeClosed = !rec.afterEscape.visible;
            const focused = await page.evaluate(() => {
              const a = document.activeElement;
              return a ? (a.id ? '#' + a.id : a.tagName) : null;
            });
            rec.focusAfter = focused;
            // MATCH BY SELECTOR, NOT BY STRING EQUALITY — comparing the focused element's id against
            // `t.opener` only works when the opener IS an id. community's thread opener is an ATTRIBUTE
            // selector ([onclick*="openThread"]) because the openers are rendered post cards, so the
            // comparison read `#reply-btn-0f78265c-... !== [onclick*="openThread"]` and reported a FALSE
            // focus-restore failure on a page that had restored focus correctly to the very element the
            // probe clicked. Asking the element whether it matches the selector is right for both forms.
            rec.focusRestored = t.openBy === 'click'
              ? await page.evaluate((sel) => {
                  const a = document.activeElement;
                  return !!(a && a.matches && a.matches(sel));
                }, t.opener)
              : null;                        // not assertable via a programmatic open — see header
            rec.ok = rec.escapeClosed && (t.openBy !== 'click' || rec.focusRestored === true);
          }
        }
      }
    }
  } catch (e) { rec.error = String(e).slice(0, 150); }
  if (rec.error) rec.ok = null;
  results.push(rec);
  console.log(`  ${t.page.padEnd(14)} ${t.view} #${t.modal.padEnd(17)} `
    + `${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : 'UNGRADED'}`
    + (rec.unreachable ? `  UNREACHABLE — ${String(rec.unreachable).slice(0, 92)}`
      : rec.error ? `  ${rec.error}`
      : `  escape-closed=${rec.escapeClosed}`
        + `  focus=${rec.focusRestored === null ? 'n/a-by-this-path' : rec.focusRestored}`
        + ` (${rec.focusAfter})`));
  // Re-establish the signed-in session for the next target, but NEVER on the anon context — signing that
  // one in would silently turn every later signed-out target into a signed-in one.
  if (!t.signedOut) await assertSignedIn(signIn(ctx, 'supervisor'));
}
await browser.close();

const graded = results.filter((r) => r.ok !== null);
const bad = graded.filter((r) => !r.ok);
writeFileSync('modal_escape_live_report.json', JSON.stringify({
  half: '2 of 2 — BEHAVIOUR. Adoption is proven from source by prove_modal_escape_adoption.mjs.',
  totals: { targets: results.length, graded: graded.length,
            ungraded: results.filter((r) => r.ok === null).length, failing: bad.length,
            focusAssertable: graded.filter((r) => typeof r.focusRestored === 'boolean').length },
  targets: results,
}, null, 1));

console.log('\n  wrote modal_escape_live_report.json');
const ung = results.filter((r) => r.ok === null);
for (const u of ung) console.log(`    UNGRADED ${u.page} #${u.modal} — ${u.error}`);
console.log(`  ${graded.length} of ${results.length} target(s) graded, ${bad.length} failing, `
  + `${graded.filter((r) => typeof r.focusRestored === 'boolean').length} with focus-restore assertable`);
if (!graded.length) {
  console.log('  FAIL — NOTHING WAS MEASURED. Zero failures over an empty denominator is not a pass.');
} else if (bad.length) {
  console.log('  FAIL — ' + bad.map((r) => `${r.page} #${r.modal}`).join('; '));
} else {
  const fa = graded.filter((r) => typeof r.focusRestored === 'boolean').length;
  console.log(`  PASS — Escape closes all ${graded.length} graded dialog(s)`
    + (fa ? `, and focus returns to the opener on all ${fa} target(s) where a real opener element was `
          + 'clicked'
          : '. Focus-restore was not assertable on any target in this run (none was opened by clicking '
          + 'a real element), so it is NOT claimed'));
}
if (GATE) process.exit(bad.length || !graded.length ? 1 : 0);
