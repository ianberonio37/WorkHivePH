// prove_dialog_a11y.mjs — CL ui-visual inside the opened V2/V3 dialog views.
//
// Same unlock as prove_dialog_layout.mjs: CL was measured at V1 and banked there, and V2/V3 stayed owed
// because nobody could open those views. The shared open-path table (tools/dialog_targets.mjs) fixes that.
//
// THREE OF CL'S FIVE ORACLES, AND THE TWO OMISSIONS ARE DELIBERATE.
//   icon_only_name  — a control a person cannot read the name of is unusable by a screen reader. Measured
//                     as: visible TEXT after stripping glyph-only content; if there is none, it needs an
//                     accessible name (aria-label, aria-labelledby, title, or an <img alt>/<svg><title>).
//                     `innerText` is NOT used — it returned '' for visible controls in an earlier arc and
//                     inflated "unnamed icon-only" from 0 to 12. textContent plus a glyph test instead.
//   focus_visible   — CAUSAL: each control is focused and its own computed style compared BEFORE and
//                     AFTER. A rule that merely EXISTS in a stylesheet proves nothing about this element,
//                     so nothing is credited from source; the indicator has to actually change (outline,
//                     outline-offset, box-shadow, border, or background).
//   reduced_motion  — emulate prefers-reduced-motion: reduce and assert nothing inside the dialog is still
//                     running a non-trivial animation or transition. A spinner is EXEMPT and counted
//                     separately: an indeterminate progress indicator that stops animating stops meaning
//                     anything, and WCAG 2.3.3 is about non-essential motion.
//   contrast_wcag / contrast_apca are NOT measured here, and that is a recorded limitation rather than an
//                     oversight: on this platform contrast is not computable from the CSSOM — uncomposited
//                     alpha gives a ratio of 1.00, and a gradient background defeats a single-colour
//                     sample. Those rows stay OWED rather than being banked from a number that would be
//                     wrong. Claiming them would be the false-green this bank exists to prevent.
//
// NON-WRITING: opens a dialog, focuses controls, reads styles, presses Escape. Types nothing, submits
// nothing. Focusing a control is not activating it.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { TARGETS } from './dialog_targets.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const NAMES = ({ id }) => {
  const dlg = document.getElementById(id);
  if (!dlg) return { present: false };
  const vis = (el) => {
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.01
           && b.width > 0 && b.height > 0;
  };
  // Glyph-only text (icon fonts, emoji, arrows, geometric shapes) is not a NAME a person can read out.
  const GLYPH = /[←-⇿⌀-➿⬀-⯿-️‍]|[\uD800-\uDBFF][\uDC00-\uDFFF]/g;
  const readable = (s) => (s || '').replace(GLYPH, '').replace(/[×✕✖✓✔·•–—…|<>+\-]/g, '')
    .replace(/\s+/g, ' ').trim();
  const out = { present: true, controls: 0, unnamed: [], skipped: {} };
  const skip = (w) => { out.skipped[w] = (out.skipped[w] || 0) + 1; };
  const SEL = 'a[href],button,input,select,textarea,summary,[role="button"],[role="tab"],[role="switch"],[role="checkbox"],[role="radio"]';
  for (const el of dlg.querySelectorAll(SEL)) {
    if (!vis(el)) { skip('not visible'); continue; }
    if (el.disabled) { skip('disabled'); continue; }
    const tag = el.tagName.toLowerCase();
    if (tag === 'input' && ['hidden'].includes((el.getAttribute('type') || '').toLowerCase())) {
      skip('hidden input'); continue;
    }
    out.controls++;
    // textContent, NOT innerText — innerText returned '' for visible controls in an earlier arc and
    // inflated the unnamed count from 0 to 12.
    const own = readable(el.textContent);
    if (own.length >= 2) continue;                       // it has readable visible text
    const aria = (el.getAttribute('aria-label') || '').trim();
    const title = (el.getAttribute('title') || '').trim();
    const lblBy = el.getAttribute('aria-labelledby');
    let byText = '';
    if (lblBy) {
      for (const rid of lblBy.split(/\s+/)) {
        const n = document.getElementById(rid);
        if (n) byText += ' ' + (n.textContent || '');
      }
    }
    let media = '';
    const img = el.querySelector('img[alt]');
    if (img) media = (img.getAttribute('alt') || '').trim();
    const svgTitle = el.querySelector('svg > title');
    if (!media && svgTitle) media = (svgTitle.textContent || '').trim();
    // A LABEL element pointing at this control also names it.
    // BOTH label forms — `for=` AND a WRAPPING label. Checking only `for=` reported 6 of hive's
    // #intent-capture radios as unnamed; every one is wrapped in `<label class="ic-opt">` carrying the full
    // option text ("Predictive maintenance: stop failures before they happen"), which is the ordinary way
    // to label a radio and names it perfectly. Same omission would have failed pm-scheduler's
    // #sheet-log-toggle. An accessible-name check that knows only one of the two label forms fails the
    // markup that uses the other.
    let assoc = '';
    if (el.id) {
      const lab = dlg.querySelector('label[for="' + el.id + '"]');
      if (lab) assoc = readable(lab.textContent);
    }
    if (!assoc) {
      const wrap = el.closest('label');
      if (wrap) assoc = readable(wrap.textContent);
    }
    // A placeholder is a weak name but it IS announced by most screen readers for text inputs.
    const ph = (el.getAttribute('placeholder') || '').trim();
    const named = [aria, title, readable(byText), media, assoc, ph].some((v) => v && v.length >= 2);
    if (!named) {
      out.unnamed.push({ tag, id: el.id || null, cls: String(el.className || '').slice(0, 30),
                         rawText: (el.textContent || '').trim().slice(0, 12) });
    }
  }
  return out;
};

// FOCUS IS DRIVEN BY THE KEYBOARD, NOT BY el.focus(), and this is the correction that matters most in this
// file. `:focus-visible` deliberately does NOT match a PROGRAMMATIC focus in Chromium — it matches when the
// browser judges the interaction keyboard-like. The first version called el.focus() and compared styles,
// and reported catastrophic-looking results: resume 0 of 3 controls with a focus indicator, achievements
// 0 of 1, inventory 7 of 25 — while index passed 9 of 9. index passes because it styles plain `:focus`;
// every other page styles `:focus-visible`, so the probe was measuring its own inability to trigger it.
// Tabbing is what a keyboard user does, so Tab is what this now does: snapshot every control unfocused,
// then Tab through the dialog and compare each stop against that element's own recorded baseline.
const SNAP_ALL = ({ id }) => {
  const dlg = document.getElementById(id);
  if (!dlg) return { present: false };
  // BLUR FIRST, or the baseline is a lie. A well-behaved dialog moves focus to its first control on open
  // (whModalA11y does exactly that), so that control's "unfocused" snapshot would actually be its FOCUSED
  // style — and it would then look unchanged when Tab arrived and be reported as having no focus
  // indicator. That is precisely what happened to resume's #rm-current-title, whose focus style
  // (border-color, resume.html:110) is real and was being cancelled out by a contaminated baseline. The
  // bug appeared only AFTER the duplicate focus trap was removed from that page, i.e. the fix that made
  // the dialog autofocus correctly is what exposed it.
  try { if (document.activeElement && dlg.contains(document.activeElement)) document.activeElement.blur(); }
  catch (_) { /* empty-catch-allow: blur is best-effort */ }
  const vis = (el) => {
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0;
  };
  const snap = (el) => {
    const s = getComputedStyle(el);
    return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.outlineOffset,
            s.boxShadow, s.borderColor, s.borderWidth, s.backgroundColor].join('|');
  };
  const SEL = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[role="button"],[role="tab"]';
  const out = {};
  let n = 0;
  for (const el of dlg.querySelectorAll(SEL)) {
    if (!vis(el) || el.disabled) continue;
    const k = 'wh-fk-' + (n++);
    el.setAttribute('data-wh-fk', k);
    out[k] = { base: snap(el), tag: el.tagName.toLowerCase(), id: el.id || null,
               cls: String(el.className || '').slice(0, 30) };
  }
  return { present: true, controls: out };
};

const READ_FOCUSED = ({ id }) => {
  const dlg = document.getElementById(id);
  const a = document.activeElement;
  if (!a || !dlg || !dlg.contains(a)) return null;
  const k = a.getAttribute('data-wh-fk');
  if (!k) return null;
  const s = getComputedStyle(a);
  return { k, now: [s.outlineStyle, s.outlineWidth, s.outlineColor, s.outlineOffset,
                    s.boxShadow, s.borderColor, s.borderWidth, s.backgroundColor].join('|'),
           focusVisible: (() => { try { return a.matches(':focus-visible'); } catch (_) { return null; } })() };
};

const MOTION = ({ id }) => {
  const dlg = document.getElementById(id);
  if (!dlg) return { present: false };
  const out = { present: true, moving: [], spinnersExempt: 0 };
  const isSpinner = (el) => /spin|loader|loading|progress|shimmer|skeleton|pulse/i
    .test((el.id || '') + ' ' + String(el.className || ''));
  for (const el of dlg.querySelectorAll('*')) {
    const s = getComputedStyle(el);
    const b = el.getBoundingClientRect();
    if (s.display === 'none' || s.visibility === 'hidden' || b.height <= 0) continue;
    // MOTION, NOT EVERY TRANSITION — and the first run proved why the distinction matters: it flagged
    // index's #signin-modal close button and both auth tabs for "still animating", when what they carry is
    // a colour transition (Tailwind's transition-colors). WCAG 2.3.3 is about non-essential MOTION; a
    // 150ms background-colour change is not motion, and reporting it as one would have banked three
    // fabricated defects on the signed-out sign-in path. So a transition only counts when it moves or
    // resizes something: transform, translate, rotate, scale, the offsets, or a dimension. A keyframe
    // ANIMATION still counts whatever it animates, because a running animation under reduced-motion is the
    // thing the media query exists to stop.
    const MOTION_PROP = /(^|[\s,])(all|transform|translate|rotate|scale|top|left|right|bottom|margin|width|height|inset)/;
    const animated = s.animationName !== 'none' && parseFloat(s.animationDuration) > 0.01;
    const transitioned = parseFloat(s.transitionDuration) > 0.01
      && MOTION_PROP.test(s.transitionProperty || '');
    if (!animated && !transitioned) continue;
    if (isSpinner(el)) { out.spinnersExempt++; continue; }
    out.moving.push({ tag: el.tagName.toLowerCase(), cls: String(el.className || '').slice(0, 30),
                      anim: s.animationName !== 'none' ? `${s.animationName} ${s.animationDuration}` : null,
                      trans: parseFloat(s.transitionDuration) > 0.01
                        ? `${s.transitionProperty} ${s.transitionDuration}` : null });
  }
  return out;
};

const browser = await chromium.launch();
const results = [];
for (const t of TARGETS.filter((x) => !ONE || x.page === ONE.replace(/\.html$/, ''))) {
  const rec = { page: t.page, view: t.view, modal: t.modal, ref: t.ref };
  if (t.notDrivable || t.unreachable) {
    rec.ok = null;
    rec.why = t.notDrivable ? `not drivable read-only: ${t.notDrivable}`
                            : `the view cannot be reached at all: ${String(t.unreachable).slice(0, 110)}`;
    results.push(rec);
    console.log(`  ${t.page.padEnd(14)} ${t.view} #${t.modal.padEnd(17)} UNGRADED  ${rec.why.slice(0, 60)}`);
    continue;
  }
  // A FRESH CONTEXT PER TARGET, because reduced-motion is emulated per context and a leaked emulation
  // would silently measure every later dialog under the wrong media state.
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  if (!t.signedOut) await assertSignedIn(signIn(ctx, 'supervisor'));
  // STATE VIEWS: install the read-failure / empty-read patch on window.fetch BEFORE the first navigation.
  // This prover already creates a fresh context per target (for reduced-motion emulation), so the injection
  // is naturally scoped and cannot leak. window.fetch and not page.route, because a warm service worker
  // bypasses route interception — the reason an earlier failure probe measured nothing while reporting
  // success. Non-writing: it only makes a READ fail or return an empty array.
  if (t.inject) await ctx.addInitScript(t.inject);
  const page = await ctx.newPage();
  try {
    const open = async () => {
      await page.goto(`${ORIGIN}/${t.page}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await page.waitForTimeout(3000);
      const landed = (page.url().split('/').pop() || '').replace(/\.html.*$/, '');
      if (landed !== t.page) throw new Error(`landed on ${landed}, not the page under test`);
      if (t.pre) {
        const pr = await page.evaluate((c) => {
          try { eval(c); return 'ok'; } catch (e) { return 'threw: ' + String(e.message || e).slice(0, 80); }
        }, t.pre);
        if (String(pr).startsWith('threw')) throw new Error(`precondition ${pr}`);
        await page.waitForTimeout(1500);
      }
      if (t.mayStartOpen) return;
      if (t.openBy === 'click') {
        const shown = await page.evaluate((sel) => {
          const el = document.querySelector(sel); if (!el) return false;
          const b = el.getBoundingClientRect(); const s = getComputedStyle(el);
          return s.display !== 'none' && s.visibility !== 'hidden' && b.height > 0;
        }, t.opener);
        if (!shown) throw new Error(`opener ${t.opener} is absent or not visible`);
        await page.click(t.opener, { timeout: 4000 });
      } else {
        const fr = await page.evaluate((c) => {
          try { eval(c); return 'ok'; } catch (e) { return 'threw: ' + String(e.message || e).slice(0, 80); }
        }, t.fn);
        if (String(fr).startsWith('threw')) throw new Error(`opener fn ${fr}`);
      }
      await page.waitForTimeout(1200);
    };
    await open();
    const openCheck = await page.evaluate(({ id }) => {
      const d = document.getElementById(id);
      if (!d) return 'absent';
      const s = getComputedStyle(d); const b = d.getBoundingClientRect();
      return (s.display !== 'none' && s.visibility !== 'hidden' && b.height > 0) ? 'open' : 'closed';
    }, { id: t.modal });
    if (openCheck !== 'open') throw new Error(`#${t.modal} is ${openCheck} — it did not open`);

    rec.names = await page.evaluate(NAMES, { id: t.modal });
    // Tab through the dialog, comparing each focused control against its OWN unfocused baseline.
    const snapAll = await page.evaluate(SNAP_ALL, { id: t.modal });
    const seen = {}; const noRing = [];
    let seeded = false;
    if (snapAll.present) {
      const total = Object.keys(snapAll.controls).length;
      // MOST of these dialogs trap focus, so a bare Tab walk cycles inside them. SOME DO NOT - an-summary,
      // levelup-overlay and exam-modal are non-trapping REGIONS, and there Tab walks straight past the
      // subtree: READ_FOCUSED is dialog-scoped, so every stop returned null, `seen` stayed empty, and the
      // view reported candidates>0 / checked=0 / noRing=[] - an abstention that reads exactly like a clean
      // pass to anything looking at the failure count. So: walk, and if nothing inside was ever reached,
      // SEED focus at the container and walk again.
      // The seed is a programmatic focus on the CONTAINER, never on a control being graded. Every reading
      // still comes from a real Tab keypress landing on the control itself, which is what :focus-visible
      // requires (see the note at the top of this file) - the seed only decides where the walk starts.
      const walk = async () => {
        for (let step = 0; step < Math.min(total * 2 + 4, 60); step++) {
          await page.keyboard.press('Tab');
          const cur = await page.evaluate(READ_FOCUSED, { id: t.modal });
          if (!cur) continue;
          if (seen[cur.k]) { if (Object.keys(seen).length >= total) break; continue; }
          seen[cur.k] = true;
          const meta = snapAll.controls[cur.k];
          if (meta && cur.now === meta.base) {
            noRing.push({ tag: meta.tag, id: meta.id, cls: meta.cls, focusVisible: cur.focusVisible });
          }
          if (Object.keys(seen).length >= total) break;
        }
      };
      await walk();
      if (!Object.keys(seen).length && total > 0) {
        seeded = await page.evaluate(({ id }) => {
          const d = document.getElementById(id);
          if (!d) return false;
          if (!d.hasAttribute('tabindex')) d.setAttribute('tabindex', '-1');
          d.focus();
          return document.activeElement === d;
        }, { id: t.modal });
        if (seeded) await walk();
      }
    }
    rec.focus = { checked: Object.keys(seen).length, noRing, seeded,
                  candidates: snapAll.present ? Object.keys(snapAll.controls).length : 0 };

    // REDUCED MOTION: re-open under the emulated media, because a dialog opened BEFORE the emulation may
    // keep the transition it was already running and read as a defect that no reduced-motion user sees.
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await open();
    await page.waitForTimeout(600);
    rec.motion = await page.evaluate(MOTION, { id: t.modal });

    rec.iconOk = rec.names.unnamed.length === 0;
    rec.focusOk = rec.focus.checked > 0 ? rec.focus.noRing.length === 0 : null;
    rec.motionOk = rec.motion.moving.length === 0;
    rec.ok = rec.iconOk && rec.motionOk && rec.focusOk !== false;
  } catch (e) { rec.error = String(e.message || e).slice(0, 150); rec.ok = null; }
  await ctx.close();
  results.push(rec);
  console.log(`  ${t.page.padEnd(14)} ${t.view} #${t.modal.padEnd(17)} `
    + `${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : 'UNGRADED'}`
    + (rec.error ? `  ${rec.error}`
      : `  named=${rec.names.controls - rec.names.unnamed.length}/${rec.names.controls}`
        + `  ring=${rec.focus.checked - rec.focus.noRing.length}/${rec.focus.checked}`
        + `  motion=${rec.motion.moving.length}${rec.motion.spinnersExempt ? `(+${rec.motion.spinnersExempt} spinner)` : ''}`));
}
await browser.close();

const graded = results.filter((r) => r.ok !== null);
const bad = graded.filter((r) => !r.ok);
// A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
// bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
// corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
writeFileSync((ONE ? 'dialog_a11y_report.partial.json' : 'dialog_a11y_report.json'), JSON.stringify({
  oracles: ['icon_only_name', 'focus_visible', 'reduced_motion'],
  notMeasured: { contrast_wcag: 'not computable from the CSSOM here — uncomposited alpha reads 1.00 and a '
                 + 'gradient defeats a single-colour sample; those rows stay OWED rather than banked wrong',
                 contrast_apca: 'same limitation' },
  totals: { targets: results.length, graded: graded.length,
            ungraded: results.filter((r) => r.ok === null).length, failing: bad.length },
  targets: results,
}, null, 1));
console.log('\n  wrote dialog_a11y_report.json');
for (const u of results.filter((r) => r.ok === null)) {
  console.log(`    UNGRADED ${u.page} ${u.view} #${u.modal} — ${(u.error || u.why || '').slice(0, 100)}`);
}
console.log(`  ${graded.length} of ${results.length} dialog(s) graded, ${bad.length} failing`);
if (!graded.length) {
  console.log('  FAIL — NOTHING WAS MEASURED. Zero failures over an empty denominator is not a pass.');
} else if (bad.length) {
  for (const r of bad) {
    console.log(`  FAIL ${r.page} ${r.view} #${r.modal}:`
      + (r.names.unnamed.length ? ` ${r.names.unnamed.length} control(s) with NO accessible name (${
          r.names.unnamed.slice(0, 3).map((u) => `${u.tag}${u.id ? '#' + u.id : '.' + u.cls}`
            + (u.rawText ? ` text="${u.rawText}"` : '')).join(', ')});` : '')
      + (r.focusOk === false ? ` ${r.focus.noRing.length} control(s) with NO focus indicator (${
          r.focus.noRing.slice(0, 3).map((u) => `${u.tag}${u.id ? '#' + u.id : '.' + u.cls}`).join(', ')});` : '')
      + (r.motion.moving.length ? ` ${r.motion.moving.length} element(s) still animating under `
          + `prefers-reduced-motion (${r.motion.moving.slice(0, 3).map((m) => `${m.tag}.${m.cls}`).join(', ')})` : ''));
  }
} else {
  console.log(`  PASS — all ${graded.length} opened dialog(s): every control has an accessible name, `
    + 'every focusable control shows a causally-verified focus indicator, and nothing animates under '
    + 'prefers-reduced-motion (spinners exempt and counted)');
}
if (GATE) process.exit(bad.length || !graded.length ? 1 : 0);
