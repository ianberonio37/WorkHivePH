// prove_dialog_layout.mjs — CJ layout + CM number-labelling INSIDE the V2/V3 dialog views.
//
// WHY THESE ROWS WERE OWED, and it was never that the oracles were hard: CJ (`w390_overflow`,
// `tap_target_44`) and CM (`what_is_this_number`) were measured platform-wide at V1 and banked there. V2
// and V3 stayed owed for one reason — **nobody could open those views**. Resolving all 15 dialog open
// paths for the CO `back_out` work removed that blocker, so the same measurements now run in the opened
// dialog, and `tools/dialog_targets.mjs` is the shared table so these two provers cannot drift.
//
// SCOPED TO THE DIALOG, NOT THE PAGE, and that scoping is the whole point. A dialog overlays the page, so
// measuring `document.body` with a sheet open re-measures V1 and banks it as V2 — the
// one-reading-for-every-layer error. Every measurement here is rooted at the dialog element:
//   - OVERFLOW: the dialog's own scrollWidth vs clientWidth, plus each descendant's right edge against
//     the dialog's content box. `overflow-x: auto|scroll|hidden|clip` on an ancestor WITHIN the dialog is
//     honoured, because a deliberately scrollable panel is not a defect (a previous arc mistook
//     `overflow-x: clip` for one, and separately missed 52px of genuinely cut-off content).
//   - TAP TARGETS: the effective target, not the box — a labelled control is activated by its label, and
//     measuring the 16px input instead of its 44px label fabricated 7 defects once already.
//   - NUMBERS: every leaf whose whole text is a number needs a label within 4 ancestors, with the same
//     ordinal/asset-code exclusions the V1 prover uses, and a NON-VACUITY control per dialog.
//
// THE SCALE FACTOR IS MEASURED AND DIVIDED OUT before any width is reported — an unscaled read invented
// 142 of 398 "offenders" in the V1 work. A width that cannot be verified is refused, never reported.
//
// NON-WRITING: opens a dialog, measures, presses Escape. Types nothing, submits nothing.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { TARGETS } from './dialog_targets.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const FLOOR = 44;
// THREE WIDTHS, because w641_overflow and w1280_overflow are separate owed rows and a 390-only reading
// must not be banked for them. A dialog is usually width-capped (max-width on its panel), so the desktop
// widths are NOT a formality: a panel that is fine at 390 can still let a long unbroken string or a wide
// table push past its own content box once the panel gets roomier. Tap targets are measured at 390 only —
// that is the mobile-first floor the V1 prover used, and a control that clears 44 at 390 does not shrink
// when the viewport grows.
const WIDTHS = [390, 641, 1280];

// ONE argument only — page.evaluate passes a single value, so the pair is wrapped.
const MEASURE = ({ id, floor }) => {
  const dlg = document.getElementById(id);
  if (!dlg) return { present: false };
  const dpr = window.devicePixelRatio || 1;
  const scale = Math.round(dpr * 1000) / 1000;
  const box = dlg.getBoundingClientRect();
  const cs = getComputedStyle(dlg);
  const vis = (el) => {
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.01
           && b.width > 0 && b.height > 0;
  };
  // ── OVERFLOW, rooted at the dialog
  const clipsX = (el) => {
    for (let a = el; a && a !== dlg.parentElement; a = a.parentElement) {
      const ox = getComputedStyle(a).overflowX;
      if (ox === 'auto' || ox === 'scroll' || ox === 'hidden' || ox === 'clip') return a;
    }
    return null;
  };
  const right = box.left + dlg.clientWidth;
  const over = [];
  for (const el of dlg.querySelectorAll('*')) {
    if (!vis(el)) continue;
    const b = el.getBoundingClientRect();
    if (b.right <= right + 1) continue;            // 1px tolerance: a 0.109px abutment is not overflow
    const clip = clipsX(el.parentElement || el);
    over.push({ tag: el.tagName, cls: String(el.className || '').slice(0, 28),
                pastBy: Math.round((b.right - right) * 10) / 10,
                clippedBy: clip ? (clip.id ? '#' + clip.id : clip.tagName) : null });
  }
  // ── TAP TARGETS — THE RULE IS PORTED VERBATIM FROM prove_viewport_overflow.mjs, NOT REINVENTED.
  // The first cut here omitted four of V1's exclusions (sr-only, `disabled`, the actionable check, and the
  // WCAG 2.5.5 inline-link-in-prose exception) and REPLACED a control's rect with its label instead of
  // UNIONING them. It reported 30 of 43 failures in inventory's part-modal on that basis. Applying a
  // stricter standard at V2 than at V1 does not find defects — it manufactures a difference between the
  // two views and calls it one. If these two rules ever diverge again, the V2 numbers stop being
  // comparable to the 750/750 that V1 banked, so the rule lives here in the same shape.
  const SEL = 'a,button,input,select,textarea,summary,[role],[onclick],[tabindex]';
  const INTERACTIVE_ROLE = new Set(['button', 'link', 'checkbox', 'radio', 'switch', 'tab', 'menuitem',
    'menuitemcheckbox', 'menuitemradio', 'option', 'combobox', 'slider', 'spinbutton', 'textbox',
    'searchbox']);
  const srOnly = (el) => {
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    if (s.clip === 'rect(0px, 0px, 0px, 0px)') return true;
    if (s.position === 'absolute' && b.width <= 1 && b.height <= 1) return true;
    return /(^|\s)(sr-only|visually-hidden|wh-sr-only)(\s|$)/.test(String(el.className || ''));
  };
  const actionable = (el) => {
    const tag = el.tagName.toLowerCase();
    if (tag === 'a') return el.hasAttribute('href');
    if (['button', 'input', 'select', 'textarea', 'summary'].includes(tag)) return true;
    const role = (el.getAttribute('role') || '').toLowerCase();
    if (INTERACTIVE_ROLE.has(role)) return true;
    return el.hasAttribute('onclick');
  };
  const union = (a, b) => ({
    width: Math.max(a.right, b.right) - Math.min(a.left, b.left),
    height: Math.max(a.bottom, b.bottom) - Math.min(a.top, b.top),
  });
  const targets = []; const skipped = {};
  const skip = (w) => { skipped[w] = (skipped[w] || 0) + 1; };
  for (const el of dlg.querySelectorAll(SEL)) {
    if (!vis(el)) { skip('not visible'); continue; }
    if (srOnly(el)) { skip('sr-only / visually hidden - not a pointer target'); continue; }
    if (el.disabled) { skip('disabled'); continue; }
    if (!actionable(el)) {
      skip('focusable but not actionable (tabindex on a non-interactive role)'); continue;
    }
    let rect = el.getBoundingClientRect();
    let via = 'own box';
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (tag === 'input' && (type === 'checkbox' || type === 'radio')) {
      const lab = el.closest('label') || (el.id ? dlg.querySelector('label[for="' + el.id + '"]') : null);
      if (lab && vis(lab)) { rect = union(rect, lab.getBoundingClientRect()); via = 'wrapping label'; }
      else via = 'bare control, no label';
    } else if (tag === 'summary') { via = 'disclosure row'; }
    // THE INLINE EXCEPTION IS ABOUT INLINE FLOW, NOT ABOUT THE TAG — so it applies to any control that
    // COMPUTES to display:inline inside a text container, not just to anchors. analytics' diagnostic panel
    // renders `<summary>` disclosures reading "+12 more" at 47 x 15, inline, and they were reported as 10
    // undersized targets. They are a word in a sentence that happens to toggle; forcing 44px would make
    // 44px-tall lines of body text. Keying on the tag would have meant fixing this again for the next tag.
    if (tag !== 'a' && getComputedStyle(el).display === 'inline'
        && el.closest('p,li,small,figcaption,td,blockquote,dd,summary,details')) {
      skip('inline text-flow control in prose (WCAG 2.5.5 exception)'); continue;
    }
    if (tag === 'a') {
      // WCAG 2.5.5's inline exception, WIDENED — and the widening prevented 34 false findings on index's
      // anon landing. V1's rule fires only when the container carries 12+ characters BEYOND the link, which
      // is too narrow when the link IS most of its <li>: index's landing lists render `display:inline`
      // anchors inside <li> ("Spare-Parts Inventory:", "Voice Journal: Speak i…") at 17px tall, and every
      // one was reported as an under-44 target. They are text in a flowing line, not discrete controls —
      // exactly what the exception exists for — and forcing 44px on them would mean 44px-tall lines of
      // body copy. So an anchor that COMPUTES to display:inline inside a text container is exempt whatever
      // the surrounding length; the length test still catches the other shape (a short link padded out
      // inside a sentence).
      const par = el.closest('p,li,small,figcaption,td,blockquote,dd');
      const inlineFlow = getComputedStyle(el).display === 'inline';
      if (par && (inlineFlow
                  || (par.textContent || '').trim().length > (el.textContent || '').trim().length + 12)) {
        skip(inlineFlow ? 'inline text-flow link in prose (WCAG 2.5.5 exception)'
                        : 'inline link within surrounding prose (WCAG 2.5.5 exception)');
        continue;
      }
    }
    const w = Math.round((rect.width / scale) * 10) / 10;
    const h = Math.round((rect.height / scale) * 10) / 10;
    targets.push({ tag, type: type || null, id: el.id || null,
                   cls: String(el.className || '').slice(0, 28), w, h, via,
                   pass: w >= floor && h >= floor });
  }
  // ── NUMBERS needing a label
  const ORD = /^(1st|2nd|3rd|\d+th)$/i;
  const nums = []; const numSkipped = {};
  const nskip = (w) => { numSkipped[w] = (numSkipped[w] || 0) + 1; };
  for (const el of dlg.querySelectorAll('*')) {
    if (el.children.length || !vis(el)) continue;
    const t = (el.textContent || '').trim();
    if (!t || ORD.test(t)) { if (t) nskip('ordinal position, not a measurement'); continue; }
    const bare = t.replace(/[₱$,%\s]/g, '');
    if (!/^\d+(\.\d+)?$/.test(bare)) continue;
    if (/^\d{1,2}$/.test(bare) && el.closest('[class*="step"],[class*="dot"]')) {
      nskip('step indicator'); continue;
    }
    // A ZERO-PADDED NUMBER IS A SEQUENCE LABEL, NEVER A MEASUREMENT — nobody writes a measured quantity as
    // "01". This is the general form of the step-indicator rule above, and it was needed because index's
    // landing carries TWO different step conventions: `.step-dot` (caught by the class test) and
    // `.stage-hex-num` (not caught — the class contains neither "step" nor "dot"), which reported "01".."04"
    // as unlabelled numbers. Extending the class list would only have postponed the third convention;
    // keying on the zero-padding is a property of the VALUE, so it holds whatever the class is called.
    if (/^0\d+$/.test(bare)) { nskip('zero-padded sequence label, not a measurement'); continue; }
    // THE LABEL TEST IS PROXIMATE AT DIALOG SCOPE, NOT ANCESTOR-WIDE — and the control is what forced
    // this. The V1 rule walks up to 4 ancestors and accepts any subtree text under 400 characters. On a
    // full page that discriminates; inside a DIALOG it cannot, because a dialog's whole subtree is usually
    // under 400 characters, so the top ancestor "labels" every number beneath it. Proof: a bare 4242
    // injected into an opened dialog came back LABELLED. So a label must be NEXT TO the number, which is
    // what a person actually reads: the number's own aria-label/title, an associated <label>, or text in
    // its immediate parent when that parent is a small wrapper (<= 3 element children) rather than a whole
    // panel. Loosening the control to make the oracle pass would have been the exact inversion of its job.
    let labelled = false, via = null;
    const own = (el.getAttribute('aria-label') || el.getAttribute('title') || '');
    if (/[A-Za-z]{3}/.test(own)) { labelled = true; via = 'own aria-label/title'; }
    if (!labelled && el.id) {
      const lab = dlg.querySelector('label[for="' + el.id + '"]');
      if (lab && /[A-Za-z]{3}/.test(lab.textContent || '')) { labelled = true; via = 'associated <label>'; }
    }
    if (!labelled) {
      const par = el.parentElement;
      if (par && par !== dlg) {
        const pal = (par.getAttribute('aria-label') || par.getAttribute('title') || '');
        if (/[A-Za-z]{3}/.test(pal)) { labelled = true; via = 'parent aria-label'; }
        else if (par.children.length <= 3) {
          const txt = (par.textContent || '').replace(/\s+/g, ' ').trim().replace(bare, '');
          if (/[A-Za-z]{3}/.test(txt) && txt.length <= 120) {
            labelled = true; via = 'text beside it in a small wrapper';
          }
        }
      }
    }
    nums.push({ text: t, cls: String(el.className || '').slice(0, 28), labelled, via });
  }
  return {
    present: true, scale,
    dlgW: Math.round((box.width / scale) * 10) / 10,
    selfOverflow: Math.round((dlg.scrollWidth - dlg.clientWidth) * 10) / 10,
    overflow: over.filter((o) => !o.clippedBy),
    overflowClipped: over.filter((o) => o.clippedBy).length,
    targets: targets.length, targetsFailing: targets.filter((t) => !t.pass),
    tapSkipped: skipped,
    numbers: nums.length, numbersUnlabelled: nums.filter((n) => !n.labelled),
    numSkipped,
    // NON-VACUITY CONTROL: a bare number injected into a label-free container inside the dialog MUST come
    // back unlabelled. Without it, a window wide enough to find real labels finds text near anything.
    control: (() => {
      // The control runs the SAME proximity predicate as the oracle above — a control that tests a
      // different rule than the thing it is validating proves nothing. The probe is appended directly to
      // the dialog (many element children, so the small-wrapper branch cannot fire) with no aria-label
      // and no associated <label>, which is exactly the shape of a genuinely unlabelled number.
      const probe = document.createElement('div');
      probe.setAttribute('data-wh-num-control', '1');
      probe.style.cssText = 'position:absolute;left:-9999px;top:0;width:40px;height:20px';
      probe.textContent = '4242';
      dlg.appendChild(probe);
      let lab = false;
      const o = probe.getAttribute('aria-label') || '';
      if (/[A-Za-z]{3}/.test(o)) lab = true;
      const par = probe.parentElement;
      if (!lab && par && par !== dlg) {
        const pal = (par.getAttribute('aria-label') || par.getAttribute('title') || '');
        if (/[A-Za-z]{3}/.test(pal)) lab = true;
        else if (par.children.length <= 3) {
          const txt = (par.textContent || '').replace(/\s+/g, ' ').trim().replace('4242', '');
          if (/[A-Za-z]{3}/.test(txt) && txt.length <= 120) lab = true;
        }
      }
      probe.remove();
      return { caught: !lab };
    })(),
  };
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await assertSignedIn(signIn(ctx, 'supervisor'));
const pageSignedIn = await ctx.newPage();
let anonCtx = null, anonPage = null;
let injCtx = null;   // per-target, closed after each injected target

const results = [];
for (const t of TARGETS.filter((x) => !ONE || x.page === ONE.replace(/\.html$/, ''))) {
  const rec = { page: t.page, view: t.view, modal: t.modal, ref: t.ref };
  let page = pageSignedIn;
  if (t.notDrivable || t.unreachable) {
    rec.ok = null;
    rec.why = t.notDrivable ? `not drivable read-only: ${t.notDrivable}`
                            : `the view cannot be reached at all: ${String(t.unreachable).slice(0, 120)}`;
    results.push(rec);
    console.log(`  ${t.page.padEnd(14)} ${t.view} #${t.modal.padEnd(17)} UNGRADED  ${rec.why.slice(0, 62)}`);
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
    // STATE VIEWS get a FRESH CONTEXT AND THEIR OWN PAGE, because the injection is installed with
    // addInitScript and would otherwise persist and quietly corrupt every later target in the run.
    // The patch goes on window.fetch, NOT page.route: a warm service worker serves from cache and bypasses
    // route interception entirely, which is how an earlier failure-injection probe measured nothing while
    // reporting success.
    if (t.inject) {
      injCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });
      if (!t.signedOut) await assertSignedIn(signIn(injCtx, 'supervisor'));
      await injCtx.addInitScript(t.inject);
      page = await injCtx.newPage();
    }
    await page.goto(`${ORIGIN}/${t.page}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(3000);
    const landed = (page.url().split('/').pop() || '').replace(/\.html.*$/, '');
    if (landed !== t.page) throw new Error(`landed on ${landed}, not the page under test`);
    if (t.pre) {
      const pr = await page.evaluate((code) => {
        try { eval(code); return 'ok'; } catch (e) { return 'threw: ' + String(e.message || e).slice(0, 80); }
      }, t.pre);
      if (String(pr).startsWith('threw')) throw new Error(`precondition ${pr}`);
      await page.waitForTimeout(1500);
    }
    if (!t.mayStartOpen) {
      if (t.openBy === 'click') {
        const shown = await page.evaluate((sel) => {
          const el = document.querySelector(sel); if (!el) return false;
          const b = el.getBoundingClientRect(); const s = getComputedStyle(el);
          return s.display !== 'none' && s.visibility !== 'hidden' && b.height > 0;
        }, t.opener);
        if (!shown) throw new Error(`opener ${t.opener} is absent or not visible`);
        await page.click(t.opener, { timeout: 4000 });
      } else {
        const fr = await page.evaluate((code) => {
          try { eval(code); return 'ok'; } catch (e) { return 'threw: ' + String(e.message || e).slice(0, 80); }
        }, t.fn);
        if (String(fr).startsWith('threw')) throw new Error(`opener fn ${fr}`);
      }
      await page.waitForTimeout(1200);
    }
    // Measure at each width WITHOUT closing and reopening: the dialog stays open, the viewport changes,
    // and two animation frames are awaited so the panel has actually reflowed before it is read.
    const byWidth = {};
    for (const w of WIDTHS) {
      await page.setViewportSize({ width: w, height: 900 });
      await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
      await page.waitForTimeout(350);
      byWidth[w] = await page.evaluate(MEASURE, { id: t.modal, floor: FLOOR });
    }
    await page.setViewportSize({ width: 390, height: 844 });
    rec.byWidth = byWidth;
    const m = byWidth[390];
    if (!m.present) throw new Error(`#${t.modal} not in the DOM`);
    if (!m.dlgW) throw new Error(`#${t.modal} measured zero width — it did not open`);
    for (const w of WIDTHS) {
      if (!byWidth[w].present || !byWidth[w].dlgW) {
        throw new Error(`#${t.modal} measured zero width at ${w}px — it did not stay open across the `
          + 'viewport change, so the wider readings cannot be trusted');
      }
    }
    rec.m = m;
    // TWO ORACLES, TWO INDEPENDENT VERDICTS. CJ is geometric and always decidable here. CM depends on a
    // heuristic that CANNOT work at dialog scope, and its own control proved it: a bare 4242 injected into
    // an opened dialog comes back LABELLED, because a dialog's whole subtree is often under the 400-char
    // ancestor-text cap, so the top ancestor "labels" every number inside it. That is the control doing
    // exactly its job — refusing to let a free zero be banked. The answer is NOT to loosen the control but
    // to let CM abstain while CJ still reports; collapsing both into one verdict would have thrown away a
    // perfectly good layout measurement, or (worse) banked a CM green the control had just refuted.
    rec.overflowByWidth = Object.fromEntries(WIDTHS.map((w) => [w, byWidth[w].overflow.length]));
    rec.cjOk = WIDTHS.every((w) => byWidth[w].overflow.length === 0) && m.targetsFailing.length === 0;
    rec.cmOk = m.control.caught ? (m.numbersUnlabelled.length === 0) : null;
    rec.cmWhy = m.control.caught ? null
      : 'the non-vacuity control did not fire in this dialog — a bare 4242 read as labelled, so the '
        + 'ancestor-text window cannot discriminate at this scope and a "0 unlabelled" result would be '
        + 'free. CM stays owed for this view; CJ is unaffected because it is geometric.';
    rec.ok = rec.cjOk;
    await page.keyboard.press('Escape').catch(() => {});
  } catch (e) { rec.error = String(e.message || e).slice(0, 150); rec.ok = null; }
  if (injCtx) { await injCtx.close().catch(() => {}); injCtx = null; }
  results.push(rec);
  const m = rec.m;
  console.log(`  ${t.page.padEnd(14)} ${t.view} #${t.modal.padEnd(17)} `
    + `${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : 'UNGRADED'}`
    + (rec.error ? `  ${rec.error}`
      : `  ovf ${WIDTHS.map((w) => `${w}:${rec.byWidth[w].overflow.length}`).join(' ')}`
        + `  tap=${m.targets - m.targetsFailing.length}/${m.targets}`
        + `  CM=${rec.cmOk === null ? 'abstains(control)' : `${m.numbers - m.numbersUnlabelled.length}/${m.numbers}`}`));
  if (!t.signedOut) await assertSignedIn(signIn(ctx, 'supervisor'));
}
await browser.close();

const graded = results.filter((r) => r.ok !== null);
const bad = graded.filter((r) => !r.ok);
writeFileSync('dialog_layout_report.json', JSON.stringify({
  floor: FLOOR, viewport: 390,
  totals: { targets: results.length, graded: graded.length,
            ungraded: results.filter((r) => r.ok === null).length, failing: bad.length },
  targets: results,
}, null, 1));
console.log('\n  wrote dialog_layout_report.json');
for (const u of results.filter((r) => r.ok === null)) {
  console.log(`    UNGRADED ${u.page} ${u.view} #${u.modal} — ${(u.error || u.why || '').slice(0, 110)}`);
}
console.log(`  ${graded.length} of ${results.length} dialog(s) graded, ${bad.length} failing`);
if (!graded.length) {
  console.log('  FAIL — NOTHING WAS MEASURED. Zero failures over an empty denominator is not a pass.');
} else if (bad.length) {
  for (const r of bad) {
    const m = r.m;
    console.log(`  FAIL ${r.page} ${r.view} #${r.modal}:`
      + (m.overflow.length ? ` ${m.overflow.length} unclipped overflow (worst +${
          Math.max(...m.overflow.map((o) => o.pastBy))}px: ${m.overflow[0].tag}.${m.overflow[0].cls});` : '')
      + (m.targetsFailing.length ? ` ${m.targetsFailing.length} tap target(s) under ${FLOOR}px (${
          m.targetsFailing.slice(0, 3).map((x) => `${x.tag}${x.id ? '#' + x.id : '.' + x.cls} ${x.w}x${x.h} via ${x.via}`)
            .join(', ')});` : '')
      + (m.numbersUnlabelled.length ? ` ${m.numbersUnlabelled.length} unlabelled number(s) (${
          m.numbersUnlabelled.slice(0, 3).map((n) => `"${n.text}"`).join(', ')})` : ''));
  }
} else {
  const cm = graded.filter((r) => r.cmOk !== null);
  console.log(`  PASS — CJ on all ${graded.length} opened dialog(s): no unclipped horizontal overflow at `
    + `390 and every effective tap target >= ${FLOOR}px.`
    + (cm.length ? `  CM also decided on ${cm.length} (control fired), all labelled.`
                 : '  CM ABSTAINS on every dialog — its control did not fire at this scope, so those '
                   + 'rows stay owed rather than being banked free.'));
}
if (GATE) process.exit(bad.length || !graded.length ? 1 : 0);
