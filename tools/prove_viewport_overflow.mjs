// prove_viewport_overflow.mjs — the CJ ui-layout width oracles, measured at a VERIFIED innerWidth.
//
// WHY THIS EXISTS ALONGSIDE page_battery.mjs: the battery already reports horizontal overflow at 390
// and 1280 and is the right harness for its four phases. This adds the three things the CJ oracles
// need and it does not have: the 641 breakpoint, a VERIFIED width, and an ancestor-clip test.
//
// THE VERIFIED WIDTH IS THE WHOLE INSTRUMENT, and it is not a formality. Driving this through the
// Playwright MCP browser, `setViewportSize({width: 390})` produced `innerWidth: 585` — a consistent
// 1.5x, because that browser runs with a scale factor. Every "390px" reading was therefore taken at
// 585px, and because the offender test compared element edges against the REQUESTED 390, it reported
// 142 offenders on index and 398 on hive. All of them were artifacts of the mismatch: at a genuinely
// verified 390 the same pages report 1 and 0. So the scale is MEASURED once (set 1000, read innerWidth)
// and every request divided by it, then re-verified per page — and a page whose width cannot be
// verified reports `verified: false` and NO offender count at all, rather than a number nobody can
// trust.
//
// AND AN ELEMENT PAST THE EDGE IS NOT AUTOMATICALLY LOST CONTENT. What survives at verified widths is
// decorative: `aurora-beam`, `aurora-blob`, `cursor-glow` — each with `overflow-x: visible` on itself
// but sitting inside an `aurora` / `aurora-bg` ancestor that clips. So the offender list is split by
// whether an ANCESTOR clips the element: an unclipped overflow can hide content and scroll the page, a
// clipped one cannot. The document-level fact is reported beside it, because
// `scrollWidth - clientWidth` is what a user actually feels as a sideways scroll — and the inverse trap
// is real too: `overflow-x: clip` can HIDE genuine content loss from scrollWidth, which is why both
// numbers are reported rather than either alone.
//
// Read-only: navigation and measurement, no clicks, no writes.
//
//   node tools/prove_viewport_overflow.mjs            # all 22 roster pages, 3 widths
//   node tools/prove_viewport_overflow.mjs --gate     # exit 1 on an UNCLIPPED overflow
//   node tools/prove_viewport_overflow.mjs --page hive
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
// IT MUST SIGN IN, AND THE FIRST VERSION DID NOT. 18 of the 22 roster pages redirect an unauthenticated
// visitor to index.html?signin=1 before rendering anything, so an anon prover measures the SIGN-IN view
// and reports it under the page's name. The tap pass is what exposed it: it found links 1365px and
// 1486px wide at a verified 390px viewport, identical on 19 pages — the signature of one shared screen
// being measured over and over, not of 19 pages. The overflow conclusion happened to agree with the
// signed-in MCP sweep, but agreeing by luck is not the same as measuring the right document, and the
// REPLAY has to measure what the row claims.
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const WIDTHS = [390, 641, 1280];
const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager',
  'dayplanner', 'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain',
  'voice-journal', 'assistant', 'community', 'public-feed', 'achievements',
  'engineering-design', 'resume', 'report-sender', 'project-report', 'analytics-report',
  // ★MARKETPLACE SURFACES, added 2026-08-20. The marketplace bank carries the SAME families
  // (BF-ui-layout, BG-ui-state, BH-ui-visual, BI-ux-comprehension) and 741 of its rows just
  // expired when utils.js moved -- but this prover's roster was the 22 PRODUCT pages, so
  // citing it for a marketplace row would claim a gate measured a surface it never opened.
  // Widening the roster is a MEASUREMENT CHANGE, not a regression: expect new findings here
  // the way the no-em-dash gate went 0 -> 299 when its glob was widened. Re-run clean and
  // confirm the teeth still fire on these surfaces BEFORE banking anything against them.
  'marketplace', 'marketplace-seller', 'marketplace-seller-profile', 'platform-actions'];

const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const TEETH = args.includes('--teeth');

const MEASURE = (target) => {
  const iw = window.innerWidth;
  const verified = Math.abs(iw - target) <= 2;
  const de = document.documentElement;
  const docOverflowPx = de.scrollWidth - de.clientWidth;
  if (!verified) return { iw, verified, docOverflowPx, offenders: null, unclipped: null };
  const vis = (el) => {
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.01
      && b.width > 0 && b.height > 0;
  };
  const clippedBy = (el) => {
    for (let a = el.parentElement; a; a = a.parentElement) {
      const s = getComputedStyle(a);
      if (s.overflowX === 'hidden' || s.overflowX === 'clip')
        return a.id || String(a.className || '').slice(0, 24) || a.tagName;
    }
    return null;
  };
  const off = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!vis(el)) continue;
    const b = el.getBoundingClientRect();
    if (b.right > iw + 1.5) off.push({
      id: el.id || null, cls: String(el.className || '').slice(0, 30),
      over: Math.round(b.right - iw), clippedByAncestor: clippedBy(el),
    });
  }
  const un = off.filter((o) => !o.clippedByAncestor);
  return {
    iw, verified, docOverflowPx, offenders: off.length, unclipped: un.length,
    worstUnclipped: un.sort((a, b) => b.over - a.over).slice(0, 4),
    sampleClipped: off.filter((o) => o.clippedByAncestor).slice(0, 2),
  };
};

// ── tap_target_44: MEASURE WHAT THE USER CLICKS, NOT THE PAINTED WIDGET ──────────────────────────
// This platform has already paid for the naive version of this check. A 22-page sweep reported six
// 13x13 failures on hive and one 18x18 on resume as real WCAG violations. Every one was a native radio
// or checkbox wrapped in a <label> — and a wrapping label IS the activation target: hive's
// `label.ic-opt` measures 293x59. The browser paints a native checkbox at 13-18px and nothing changes
// that without `appearance: none`, so a probe reading the input's own rect reports a defect on the
// CORRECT pattern and stays silent on the broken one (a bare checkbox with no label). It inverts the
// signal. That sweep produced four false-positive families that all rhyme — sr-only boxes, decorative
// blobs, a declared ellipsis, and a labelled target — and in each case the element was DECLARING what
// it was while a raw geometric number got measured instead.
//
// So the effective target is resolved before anything is judged:
//   input[checkbox|radio]  -> union with its wrapping <label> or label[for=id]
//   <summary>              -> the whole disclosure row is the target
//   sr-only / clipped      -> not a pointer target at all, excluded
//   inline link in prose   -> WCAG 2.5.5 explicitly exempts links inline in a sentence
// Every exclusion is counted and reported, so none of it is silent.
const TAP = (target) => {
  const iw = window.innerWidth;
  if (Math.abs(iw - target) > 2) return { verified: false, iw };
  const cs = (el) => getComputedStyle(el);
  const vis = (el) => {
    const s = cs(el); const b = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.01
      && b.width > 0 && b.height > 0;
  };
  const srOnly = (el) => {
    const s = cs(el); const b = el.getBoundingClientRect();
    return (b.width <= 2 && b.height <= 2)
      || s.clipPath === 'inset(50%)'
      || /(^|\s)(sr-only|visually-hidden|screen-reader-only)(\s|$)/.test(el.className || '');
  };
  const union = (a, b) => ({
    width: Math.max(a.right, b.right) - Math.min(a.left, b.left),
    height: Math.max(a.bottom, b.bottom) - Math.min(a.top, b.top),
  });
  const out = { verified: true, iw, checked: 0, pass: 0, small: [], skipped: 0, skipReasons: {} };
  const skip = (why) => { out.skipped++; out.skipReasons[why] = (out.skipReasons[why] || 0) + 1; };
  const SEL = 'a[href],button,input,select,textarea,summary,[role="button"],[role="tab"],'
    + '[role="switch"],[role="checkbox"],[onclick],[tabindex]:not([tabindex="-1"])';
  // A TARGET MUST BE ACTIONABLE. `[tabindex="0"]` alone is FOCUS MANAGEMENT, not a pointer target:
  // community's `#presence-bar` is role="region" aria-label="Members online" with tabindex 0, no
  // onclick, no inner controls and cursor:auto — a landmark made keyboard-reachable so it can be read.
  // It measured 335x40 and was reported as a 4px-short tap failure. WCAG target-size governs things
  // that PERFORM an action; tabbing to a region to read it is not one. This is the same family as the
  // four false positives above — the element declared what it was (role=region) and its box got
  // measured anyway.
  const INTERACTIVE_ROLE = new Set(['button', 'link', 'tab', 'switch', 'checkbox', 'radio',
    'menuitem', 'menuitemcheckbox', 'menuitemradio', 'option', 'combobox', 'slider', 'spinbutton']);
  const actionable = (el) => {
    const tag = el.tagName.toLowerCase();
    if (tag === 'a') return el.hasAttribute('href');
    if (['button', 'input', 'select', 'textarea', 'summary'].includes(tag)) return true;
    const role = (el.getAttribute('role') || '').toLowerCase();
    if (INTERACTIVE_ROLE.has(role)) return true;
    if (el.hasAttribute('onclick')) return true;
    return false;
  };
  for (const el of document.querySelectorAll(SEL)) {
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
      const lab = el.closest('label')
        || (el.id ? document.querySelector('label[for="' + el.id + '"]') : null);
      if (lab && vis(lab)) { rect = union(rect, lab.getBoundingClientRect()); via = 'wrapping label'; }
      else via = 'bare control, no label';
    } else if (tag === 'summary') {
      via = 'disclosure row';
    }
    if (tag === 'a') {
      const par = el.closest('p,li,small,figcaption,td');
      if (par && (par.textContent || '').trim().length > (el.textContent || '').trim().length + 12) {
        skip('inline link within surrounding prose (WCAG 2.5.5 exception)'); continue;
      }
    }
    out.checked++;
    if (rect.width >= 44 && rect.height >= 44) out.pass++;
    else if (out.small.length < 8) out.small.push({
      tag, type: type || null, id: el.id || null, cls: String(el.className || '').slice(0, 28),
      w: Math.round(rect.width), h: Math.round(rect.height), via,
      text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30),
    });
  }
  out.tooSmall = out.checked - out.pass;
  return out;
};

// ── safe_area: DOES FIXED CHROME RESPECT THE NOTCH AND THE HOME BAR? ─────────────────────────────
// On a notched phone the browser reports `env(safe-area-inset-bottom)` and anything pinned to the
// bottom edge sits UNDER the home bar unless it adds that inset. Headless chromium has no insets, so
// env() resolves to 0 and the EFFECT cannot be observed here — only the DECLARATION can. That limit is
// stated rather than papered over: this measures whether every bottom- or top-pinned fixed element is
// covered by a rule that mentions safe-area-inset, which is the thing a person can actually fix. It
// does NOT prove the rendering on a real iPhone, and a row banked from it must say so.
const SAFE = () => {
  const insetRe = /safe-area-inset/;
  // Which CSS rules on this page mention the insets at all, and for which selectors.
  const rules = [];
  for (const sheet of document.styleSheets) {
    let list;
    try { list = sheet.cssRules; } catch (e) { continue; }   // cross-origin sheet, unreadable
    const walk = (rs) => {
      for (const r of rs) {
        if (r.cssRules) { walk(r.cssRules); continue; }
        if (r.selectorText && insetRe.test(r.cssText)) rules.push(r.selectorText);
      }
    };
    walk(list);
  }
  // COVERAGE CAN LIVE IN AN INLINE style ATTRIBUTE, AND MISSING THAT READ AS A PLATFORM GAP.
  // The CSSOM-only version reported `insetRules: 0` on hive — while hive.html contains FIVE
  // safe-area-inset uses. They are written inline (`<div id="intent-capture" style="position:fixed;
  // …">`), which `document.styleSheets` never sees. So an element counts as covered if a stylesheet
  // rule matches it OR its own inline style mentions the inset OR an ancestor's does, since padding on
  // a wrapper protects what is inside it.
  const inlineHasInset = (el) => {
    for (let a = el; a; a = a.parentElement) {
      const raw = a.getAttribute && a.getAttribute('style');
      if (raw && insetRe.test(raw)) return true;
    }
    return false;
  };
  const covered = (el) => inlineHasInset(el)
    || rules.some((sel) => { try { return el.matches(sel); } catch (e) { return false; } });
  const vis = (el) => {
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.01
      && b.width > 0 && b.height > 0;
  };
  // ONLY CHROME A PERSON READS OR TOUCHES COUNTS. The first version swept every fixed/sticky element
  // pinned to an edge and reported 44 of 44 uncovered on all 22 pages — a 100% failure rate, which is
  // the signature of a broken instrument, not a broken platform. What it had caught was `wh-skip-link`
  // (visually hidden until focused), `cursor-glow` (decoration) and `aurora-bg` (a full-screen
  // background): none of them is notch-facing chrome, and none is what the platform's 50
  // `env(safe-area-inset-bottom)` rules target. So an edge-pinned element counts only if it carries
  // actual content — a control or visible text — which is what would sit under the home bar.
  const meaningful = (el) => {
    if (/skip-link|cursor-glow|aurora|hex-pattern|backdrop|overlay-bg/i.test(
      (el.id || '') + ' ' + (el.className || ''))) return false;
    // A MODAL IS NOT EDGE CHROME. hive's `#intent-capture` is role="dialog" aria-modal="true" and
    // position:fixed, so an edge test catches it — but a dialog is a temporary overlay, not the
    // persistent bar that sits under the home bar. Its own layout owns its insets.
    const role = (el.getAttribute('role') || '').toLowerCase();
    if (role === 'dialog' || role === 'alertdialog' || el.getAttribute('aria-modal') === 'true') {
      return false;
    }
    if (el.querySelector('a[href],button,input,select,textarea,[role="button"]')) return true;
    return (el.textContent || '').trim().length > 0;
  };
  const pinned = [];
  const decorative = [];
  for (const el of document.querySelectorAll('body *')) {
    const s = getComputedStyle(el);
    if (s.position !== 'fixed' && s.position !== 'sticky') continue;
    if (!vis(el)) continue;
    const atBottom = s.bottom !== 'auto' && Math.abs(parseFloat(s.bottom) || 0) <= 2;
    const atTop = s.top !== 'auto' && Math.abs(parseFloat(s.top) || 0) <= 2;
    if (!atBottom && !atTop) continue;
    const rec = {
      id: el.id || null, cls: String(el.className || '').slice(0, 30), edge: atBottom ? 'bottom' : 'top',
      padB: s.paddingBottom, padT: s.paddingTop, covered: covered(el),
    };
    if (!meaningful(el)) { decorative.push(rec); continue; }
    pinned.push(rec);
  }
  return {
    insetRules: rules.length, sampleRules: rules.slice(0, 4),
    pinned: pinned.length, uncovered: pinned.filter((x) => !x.covered).length,
    worst: pinned.filter((x) => !x.covered).slice(0, 5),
    decorativeSkipped: decorative.length,
    decorativeSample: decorative.slice(0, 3).map((d) => (d.id || d.cls) + '@' + d.edge),
    // NON-VACUITY: if this page declares viewport-fit=cover it has OPTED INTO the unsafe area, so the
    // question is live. Without cover the browser letterboxes and insets are irrelevant by construction
    // — a pass there is free and is reported as not-applicable rather than as proof.
    viewportFitCover: /viewport-fit\s*=\s*cover/.test(
      (document.querySelector('meta[name="viewport"]') || {}).content || ''),
  };
};

const browser = await chromium.launch();
const ctx = await browser.newContext();
await assertSignedIn(signIn(ctx, 'supervisor'));
const page = await ctx.newPage();

// MEASURE the scale rather than assume it is 1.
await page.setViewportSize({ width: 1000, height: 800 });
await page.goto(`${ORIGIN}/index.html`, { waitUntil: 'domcontentloaded' }).catch(() => {});
const scale = (await page.evaluate(() => window.innerWidth)) / 1000 || 1;

const results = [];
for (const p of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  const rec = { page: p, w: {} };
  for (const target of WIDTHS) {
    await page.setViewportSize({ width: Math.round(target / scale), height: 900 });
    try {
      await page.goto(`${ORIGIN}/${p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
      await page.waitForTimeout(2400);
      // DID WE LAND ON THE PAGE WE ASKED FOR? A redirect to the sign-in screen renders a real, clean
      // document — so without this check the measurement succeeds and is filed under the wrong name.
      const landed = await page.evaluate(() => location.pathname + location.search);
      rec.landed = landed;
      if (!landed.includes(p)) {
        rec.w[target] = { redirected: landed, verified: null, unclipped: null };
        continue;
      }
      if (TEETH && target === 390) {
        // Planted pair for BOTH oracles this prover settles, injected after settle and BEFORE
        // MEASURE/TAP so it flows through the REAL lenses rather than a second copy of them.
        rec.teethExpect = await page.evaluate(() => {
          const mk = (id, css, tag) => {
            const d = document.createElement(tag || 'div');
            d.id = id; d.textContent = 'x'; d.style.cssText = css;
            document.body.appendChild(d); return d;
          };
          mk('wh-teeth-of-violator', 'position:absolute;left:100%;width:400px;height:20px');
          mk('wh-teeth-of-satisfier', 'position:absolute;left:0;width:40px;height:20px');
          mk('wh-teeth-tap-violator', 'width:30px;height:30px', 'button');
          mk('wh-teeth-tap-satisfier', 'width:60px;height:60px', 'button');
          // COMPUTED, NOT ASSUMED -- see note 2 in .tmp/add_teeth_cj_ck.py.
          let clips = null;
          for (let a = document.getElementById('wh-teeth-of-violator').parentElement; a; a = a.parentElement) {
            const cs = getComputedStyle(a);
            if (cs.overflowX === 'hidden' || cs.overflowX === 'clip') { clips = a.tagName; break; }
          }
          return { bodyClipsX: clips };
        });
      }
      rec.w[target] = await page.evaluate(MEASURE, target);
      // 390 is where thumb reach actually matters, so the tap-target pass runs there.
      if (target === 390) {
        rec.tap = await page.evaluate(TAP, target);
        rec.safe = await page.evaluate(SAFE);
      }
    } catch (e) {
      rec.w[target] = { error: String(e).slice(0, 120) };
    }
  }
  if (TEETH && rec.teethExpect) {
    const m = rec.w[390] || {}, tp = rec.tap || {};
    const has = (arr, id) => (arr || []).some((x) => (x.id || '') === id);
    // When an ancestor clips, the violator correctly lands in `offenders` but NOT in `unclipped`.
    const oCaught = rec.teethExpect.bodyClipsX
      ? (m.offenders || 0) > 0
      : has(m.worstUnclipped, 'wh-teeth-of-violator');
    rec.teeth = {
      overflowCaught: oCaught,
      overflowSatisfierClean: !has(m.worstUnclipped, 'wh-teeth-of-satisfier'),
      tapCaught: has(tp.small, 'wh-teeth-tap-violator'),
      tapSatisfierClean: !has(tp.small, 'wh-teeth-tap-satisfier'),
      clippedAt: rec.teethExpect.bodyClipsX,
    };
    rec.teeth.ok = rec.teeth.overflowCaught && rec.teeth.overflowSatisfierClean
                && rec.teeth.tapCaught && rec.teeth.tapSatisfierClean;
    if (!rec.teeth.ok) { console.log('    BLUNT ' + rec.page + ': ' + JSON.stringify(rec.teeth)); process.exitCode = 1; }
    else console.log('    TEETH ok ' + rec.page + (rec.teeth.clippedAt ? ' (clipped at ' + rec.teeth.clippedAt + ')' : ''));
  }
  results.push(rec);
  const tap = rec.tap || {};
  const bad = WIDTHS.filter((w) => (rec.w[w] || {}).unclipped);
  const unver = WIDTHS.filter((w) => (rec.w[w] || {}).verified === false);
  console.log(`  ${p.padEnd(20)} ${bad.length ? 'UNCLIPPED@' + bad.join(',')
    : rec.landed && !rec.landed.includes(p) ? 'REDIRECTED->' + rec.landed
    : unver.length ? 'UNVERIFIED@' + unver.join(',') : 'clean@390/641/1280'}`
    + `  tap: ${tap.pass || 0}/${tap.checked || 0}`
    + (tap.tooSmall ? `  ${tap.tooSmall} SMALL: ` + (tap.small || []).slice(0, 2)
        .map((x) => `${x.tag}${x.id ? '#' + x.id : ''} ${x.w}x${x.h} via ${x.via}`).join('; ') : '')
    + `  safe: ${(rec.safe || {}).pinned || 0} pinned`
    + ((rec.safe || {}).uncovered ? ` ${rec.safe.uncovered} UNCOVERED: ` + (rec.safe.worst || [])
        .slice(0, 2).map((x) => `${x.id || x.cls}@${x.edge}`).join('; ') : ''));
}
await browser.close();

const redirected = results.filter((r) => WIDTHS.some((w) => (r.w[w] || {}).redirected));
const unverified = results.filter((r) => WIDTHS.some((w) => (r.w[w] || {}).verified === false));
const offending = results.filter((r) => WIDTHS.some((w) => (r.w[w] || {}).unclipped));
const tapBad = results.filter((r) => (r.tap || {}).tooSmall);
writeFileSync('viewport_overflow_report.json', JSON.stringify({
  ran: new Date().toISOString(), origin: ORIGIN, scale, widths: WIDTHS,
  pages: results, unverified: unverified.map((r) => r.page), offending: offending.map((r) => r.page),
  tapOffending: tapBad.map((r) => r.page), redirected: redirected.map((r) => r.page),
  safeOffending: results.filter((r) => (r.safe || {}).uncovered).map((r) => r.page),
  safeTotals: {
    pinned: results.reduce((a, r) => a + ((r.safe || {}).pinned || 0), 0),
    uncovered: results.reduce((a, r) => a + ((r.safe || {}).uncovered || 0), 0),
  },
  tapTotals: {
    checked: results.reduce((a, r) => a + ((r.tap || {}).checked || 0), 0),
    pass: results.reduce((a, r) => a + ((r.tap || {}).pass || 0), 0),
    tooSmall: results.reduce((a, r) => a + ((r.tap || {}).tooSmall || 0), 0),
    skipped: results.reduce((a, r) => a + ((r.tap || {}).skipped || 0), 0),
  },
}, null, 1));

console.log(`\n  ${results.length} page(s) x ${WIDTHS.length} verified width(s) — `
  + `${offending.length} with an UNCLIPPED overflow, ${unverified.length} unverifiable  `
  + `(scale ${scale})`);
console.log('  wrote viewport_overflow_report.json');
if (GATE) {
  if (redirected.length) {
    console.log('  FAIL — these pages redirected instead of rendering, so nothing was measured for '
      + 'them: ' + redirected.map((r) => `${r.page}->${r.landed}`).join(', '));
    process.exit(1);
  }
  if (unverified.length) {
    console.log(`  FAIL — width could not be verified on: ${unverified.map((r) => r.page).join(', ')}`);
    process.exit(1);
  }
  if (offending.length) {
    console.log(`  FAIL — unclipped horizontal overflow on: ${offending.map((r) => r.page).join(', ')}`);
    process.exit(1);
  }
  // safe_area IS REPORTED, NOT GATED, AND THE REASON IS THE INSTRUMENT'S OWN LIMIT.
  // Headless chromium exposes NO safe-area insets, so `env(safe-area-inset-bottom)` computes to 0px and
  // the EFFECT is unobservable here — only the DECLARATION can be checked, and that check was wrong four
  // times in a row. It reported 44 of 44 uncovered (it was measuring `wh-skip-link`, `cursor-glow` and
  // `aurora-bg`), then hive's `#intent-capture` (a role="dialog" modal, not edge chrome), then hive with
  // `insetRules: 0` while hive.html contains five inset uses written inline, and finally
  // pm-scheduler's `.bottom-nav` — which declares `padding-bottom: env(safe-area-inset-bottom)` at
  // pm-scheduler.html:226. Each time the element was DECLARING what it was and a computed number got
  // believed instead.
  // A gate that has been wrong four times about the same property should not be able to fail a build, so
  // the counts are reported for a person to read and `safe_area` STAYS OWED rather than being banked off
  // this. Proving it needs a device or emulation that actually reports insets.
  const safeBad = results.filter((r) => (r.safe || {}).uncovered);
  if (safeBad.length) {
    console.log('  NOTE (not gated) — edge-pinned chrome this check could not confirm an inset rule for: '
      + safeBad.map((r) => `${r.page}:${(r.safe.worst[0] || {}).cls || ''}`).join(', ')
      + '\n         Headless reports NO insets so env() computes to 0px; this check has produced four '
      + 'false readings and is INFORMATIONAL only. safe_area stays owed.');
  }
  if (tapBad.length) {
    console.log('  FAIL — tap targets under 44px at a verified 390 on: '
      + tapBad.map((r) => r.page).join(', '));
    process.exit(1);
  }
  console.log('  PASS — no unclipped horizontal overflow at any verified width, and every effective '
    + 'tap target clears 44px at 390');
}
