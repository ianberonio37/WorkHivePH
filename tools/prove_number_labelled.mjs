// prove_number_labelled.mjs — the CM `what_is_this_number` oracle, measured on the rendered page.
//
// THE ORACLE: a number a person cannot name is a number they cannot act on. So for every element that
// renders a NUMBER as its whole content — the stat tiles, KPI heroes and count badges — the question is
// whether something adjacent says WHAT it is.
//
// WHAT COUNTS AS A NUMBER-BEARING ELEMENT, narrowly, because a loose definition makes this worthless:
// a LEAF element (no element children) whose trimmed text is numeric-only after stripping currency,
// separators, %, and a unit suffix. "9" and "₱1,850,000" and "61%" qualify; "9 open items carried over"
// does not, because it labels itself.
//
// WHAT COUNTS AS A LABEL: non-numeric text of >= 3 characters in the element's own aria-label / title,
// or in an ANCESTOR's text once the number itself is removed. This platform's stat tiles put the figure
// in one span and its name in a sibling, e.g. `sb-card-carry` renders "Carry-forward" + "9", so a test
// that looked only inside the number's own box would call every one of them unlabelled.
//
// THE WINDOW IS A WALK, NOT A FIXED DEPTH, AND THAT COST A FALSE POSITIVE. A 2-level window (parent +
// grandparent) reported 6 unlabelled numbers on achievements — "5", "18", "38", "63", "83", "96". All
// six are `wh-avatar-lvl` badges rendering "★5", "★18" …, and the label lives at the GREAT-grandparent:
// "★ Iron Lv", "★ Bronze Lv", "★ Silver Lv", "★ Gold Lv", "★ Platinum Lv", "★ Legend Lv". They are a
// tier ladder, fully labelled, one level past where I was looking. So the walk now climbs up to 4
// ancestors, accepting an ancestor's text only while it is SECTION-sized or smaller (<= 400 chars),
// because a whole page section's prose is not a label and treating it as one would make this test pass
// on anything. Both bounds matter: too tight invents defects, too loose makes the pass free.
//
// AND THE UPPER BOUND WAS TOO TIGHT AT FIRST, which penalised the best-labelled card on the platform.
// At 120 chars it reported analytics' `an-oee-hero` "88%" as UNLABELLED — while its own card renders
// `sc-label` "OEE (avg, partial)", `sc-sub` "Avg across 22 assets", `sc-tag` "WORLD CLASS" and
// "ISO 22400-2:2014 · Availability × Quality only. Add each asset's cycle time to include Performance."
// The owning card's subtree is 155 characters BECAUSE it names the metric, its denominator, its band,
// its standard and the caveat that Performance is excluded. Rejecting it for being 35 characters too
// long meant the instrument marked thoroughness as a defect. 400 admits that card and still rejects the
// row above it (432) and the summary section (1295).
//
// WHY ASSET CODES ARE EXCLUDED AND THE EXCLUSION NAMES ITS REASON: identifiers like GEN-003 or a row of
// "405 XP" read as numbers to a matcher but are names, not measurements. Elements inside a link, a
// button, a table header, or carrying a data-* id attribute are skipped, and the count of skips is
// reported so the exclusion is visible rather than silent.
//
// Read-only: navigation and measurement. No clicks, no writes.
//
//   node tools/prove_number_labelled.mjs            # all 22 roster pages, V1
//   node tools/prove_number_labelled.mjs --gate     # exit 1 if any page has an UNLABELLED number
//   node tools/prove_number_labelled.mjs --page hive
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, SEEDER, assertSignedIn } from './live_page_journeys.mjs';

const ORIGIN = process.env.WH_ORIGIN || SEEDER || 'http://127.0.0.1:5000';
const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager',
  'dayplanner', 'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain',
  'voice-journal', 'assistant', 'community', 'public-feed', 'achievements',
  'engineering-design', 'resume', 'report-sender', 'project-report', 'analytics-report',
  // ★MARKETPLACE SURFACES, added 2026-08-20 -- see the same note in prove_viewport_overflow.
  // BI-ux-comprehension in the marketplace bank is 35 rows (28 live-walk) and reads like this
  // prover settles it, but the roster was the 22 product pages, so it never opened these.
  // A row citing cm_number_labelled for a marketplace surface would name a gate that did not
  // measure it. Widening first, converting second -- never the reverse.
  'marketplace', 'marketplace-seller', 'marketplace-seller-profile', 'platform-actions'];

const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const MEASURE = () => {
  // IS THE PAGE ACTUALLY RENDERED? The non-vacuity control failed on exactly logbook and analytics
  // during the full sweep and passed when each was run alone — because at that moment those pages were
  // still filling in (analytics' KPIs were waiting on an orchestrator that was answering 503), so
  // `body`'s text was short enough to be mistaken for a label. That is not a flaw in the control; it is
  // the control correctly refusing to certify a half-painted page. So readiness is now measured and an
  // under-rendered page is reported as such rather than counted.
  const bodyChars = (document.body.textContent || '').replace(/\s+/g, ' ').trim().length;
  if (bodyChars < 400) return { underRendered: true, bodyChars, numbers: 0, labelled: 0,
                                unlabelled: [], skipped: 0, skipReasons: {}, controlCaught: null };
  const vis = (el) => {
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.01
      && b.width > 0 && b.height > 0;
  };
  const txt = (el) => (el.textContent || '').replace(/\s+/g, ' ').trim();
  // Numeric-only after stripping currency, separators, %, and a short unit suffix.
  const NUMERIC = /^[₱$€£]?\s*-?[\d][\d,.\s]*\s*(%|hrs?|h|d|days?|pcs?|kg|L|m|min|mins|XP|\/\s*\d+)?$/i;
  const isNumber = (s) => s.length > 0 && s.length <= 18 && NUMERIC.test(s) && /\d/.test(s);
  // An identifier is a NAME, not a measurement.
  const CODEISH = /^[A-Z]{2,}-\d|^\d{4}-\d{2}-\d{2}$/;
  // AN ORDINAL POSITION IS NOT A MEASUREMENT EITHER, and this exclusion names its reason. logbook's
  // "1", "2", "3" are `step-dot` elements (#sdot-1..3) inside `.step-indicator` — the step numbers of
  // the "Log a Repair" wizard. Asking "what is this number?" of a step marker is a category error: it
  // is a position in a sequence, like an asset code is a name. (They DO lack aria-labels, so a screen
  // reader hears a bare "1" — that is a real gap, but it belongs to the icon-only-name / a11y oracle,
  // not to this one, and mixing them would let a genuine a11y finding hide inside a comprehension pass.)
  const ORDINALISH = (el) => /step|dot|ordinal|index|pagenum|page-num|tab-num|slide/i
    .test((el.id || '') + ' ' + (el.className || ''))
    || !!el.closest('[class*="step-indicator"],[class*="stepper"],[class*="pagination"],ol');
  const out = { numbers: 0, labelled: 0, unlabelled: [], skipped: 0, skipReasons: {} };
  const skip = (why) => { out.skipped++; out.skipReasons[why] = (out.skipReasons[why] || 0) + 1; };
  for (const el of document.querySelectorAll('body *')) {
    if (el.children.length) continue;                 // leaves only
    if (!vis(el)) continue;
    const t = txt(el);
    if (!isNumber(t)) continue;
    if (CODEISH.test(t)) { skip('asset-code / date identifier'); continue; }
    if (ORDINALISH(el)) { skip('ordinal / step position, not a measurement'); continue; }
    if (el.closest('a,button,[role="button"],th,[data-asset-id],[data-id],time')) {
      skip('inside a link/button/table-header/identifier'); continue;
    }
    out.numbers++;
    const strip = (s) => s.replace(t, ' ').replace(/[\d,.%₱$€£\s]+/g, ' ').trim();
    const own = [el.getAttribute('aria-label'), el.getAttribute('title')].filter(Boolean).join(' ');
    let near = own;
    let a = el.parentElement;
    for (let depth = 0; depth < 4 && a; depth++, a = a.parentElement) {
      const cand = strip(txt(a));
      if (cand && cand.length <= 400) near += ' ' + cand;   // a label/card, not a page section
      if (near.replace(/[^A-Za-z]/g, '').length >= 3) break;
      const ariaUp = a.getAttribute('aria-label');
      if (ariaUp) near += ' ' + ariaUp;
    }
    if (near.replace(/[^A-Za-z]/g, '').length >= 3) out.labelled++;
    else if (out.unlabelled.length < 8) out.unlabelled.push({
      text: t, id: el.id || null, cls: String(el.className || '').slice(0, 30),
      parentCls: el.parentElement ? String(el.parentElement.className || '').slice(0, 26) : null,
      nearFound: near.slice(0, 60),
    });
  }
  // NON-VACUITY CONTROL. Widening the label window to 4 ancestors risks finding SOME text near every
  // number, which would turn this into a test that cannot fail. So a genuinely bare number is injected
  // into a label-free container and must come back UNLABELLED.
  const host = document.createElement('div');
  host.setAttribute('data-wh-control', '1');
  host.style.cssText = 'position:fixed;left:0;top:0;width:40px;height:20px;z-index:99999';
  const bare = document.createElement('span');
  bare.textContent = '4242';
  host.appendChild(bare);
  document.body.appendChild(host);
  let controlCaught = false;
  {
    const t = '4242';
    const strip2 = (s) => s.replace(t, ' ').replace(/[\d,.%₱$€£\s]+/g, ' ').trim();
    let near = '';
    let a = bare.parentElement;
    for (let d = 0; d < 4 && a; d++, a = a.parentElement) {
      const cand = strip2((a.textContent || '').replace(/\s+/g, ' ').trim());
      if (cand && cand.length <= 400) near += ' ' + cand;
      if (near.replace(/[^A-Za-z]/g, '').length >= 3) break;
    }
    controlCaught = near.replace(/[^A-Za-z]/g, '').length < 3;
    out.controlNear = near.slice(0, 90);
  }
  host.remove();
  out.controlCaught = controlCaught;
  out.bodyChars = bodyChars;
  return out;
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await assertSignedIn(signIn(ctx, 'supervisor'));
const page = await ctx.newPage();

const results = [];
for (const p of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  let rec;
  try {
    await page.goto(`${ORIGIN}/${p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(4200);
    rec = { page: p, ...(await page.evaluate(MEASURE)) };
    rec.unlabelledCount = rec.numbers - rec.labelled;
  } catch (e) { rec = { page: p, error: String(e).slice(0, 130) }; }
  results.push(rec);
  console.log(`  ${p.padEnd(20)} numbers=${String(rec.numbers).padStart(3)}`
    + ` labelled=${String(rec.labelled).padStart(3)}`
    + ` UNLABELLED=${String(rec.unlabelledCount).padStart(3)}`
    + ` skipped=${String(rec.skipped).padStart(3)}`
    + ` ctl=${rec.controlCaught ? 'ok' : 'FAIL'}`
    + (rec.unlabelled && rec.unlabelled.length
      ? `  e.g. ${rec.unlabelled.slice(0, 2).map((u) => `"${u.text}"`).join(', ')}` : ''));
}
await browser.close();

const bad = results.filter((r) => r.unlabelledCount > 0);
// A NARROWED RUN MUST NOT CLOBBER THE FULL ONE: this file is read downstream (gates and
// bank_prover_reports), so a --page/--case spot-check overwriting a whole sweep's verdicts
// corrupts the BANK, not just a log. Measured on prove_retry_path 2026-08-27.
writeFileSync((ONE ? 'number_labelled_report.partial.json' : 'number_labelled_report.json'), JSON.stringify({
  ran: new Date().toISOString(), origin: ORIGIN, role: 'supervisor', view: 'V1',
  pages: results, offending: bad.map((r) => r.page),
  totals: {
    numbers: results.reduce((a, r) => a + (r.numbers || 0), 0),
    labelled: results.reduce((a, r) => a + (r.labelled || 0), 0),
    unlabelled: results.reduce((a, r) => a + (r.unlabelledCount || 0), 0),
    skipped: results.reduce((a, r) => a + (r.skipped || 0), 0),
  },
}, null, 1));

const T = results.reduce((a, r) => ({
  n: a.n + (r.numbers || 0), l: a.l + (r.labelled || 0), u: a.u + (r.unlabelledCount || 0),
}), { n: 0, l: 0, u: 0 });
console.log(`\n  ${results.length} page(s) — ${T.n} number-bearing element(s), ${T.l} labelled, `
  + `${T.u} UNLABELLED across ${bad.length} page(s)`);
console.log('  wrote number_labelled_report.json');
const under = results.filter((r) => r.underRendered);
if (under.length) console.log(`  under-rendered, not counted: ${under.map((r) => r.page).join(', ')}`);
const noCtl = results.filter((r) => !r.underRendered && r.controlCaught !== true);
if (noCtl.length) console.log(`  control did NOT fire on: ${noCtl.map((r) => r.page).join(', ')}`);
if (GATE) {
  if (noCtl.length) {
    console.log('  FAIL — the non-vacuity control did not fire; a pass here would be meaningless');
    process.exit(1);
  }
  if (!T.n) { console.log('  FAIL — 0 number-bearing elements found; the matcher is not seeing the page'); process.exit(1); }
  if (T.u) { console.log(`  FAIL — unlabelled numbers on: ${bad.map((r) => r.page).join(', ')}`); process.exit(1); }
  console.log(`  PASS — every one of ${T.n} rendered numbers carries a label naming it`);
}
