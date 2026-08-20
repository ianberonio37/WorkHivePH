// prove_units_visible.mjs — the CE `units_visible` oracle, measured on the rendered page.
//
// THE ORACLE, verbatim: "the unit is on screen beside the number, not implied by position."
//
// ★THE HARD PART IS NOT FINDING NUMBERS, IT IS KNOWING WHICH ONES OWE A UNIT. Most numbers on this
// platform are COUNTS — 9 open jobs, 3 low-stock parts, 28 PMs overdue — and a count has no unit to
// show. Flagging those would redden every surface, and a check that reddens everything is measuring
// itself rather than the product. So the test is conditional, and the condition is the whole design:
//
//   IF THE LABEL NAMES A DIMENSION, THE VALUE MUST CARRY ITS UNIT.
//
// A tile labelled "MTBF" showing "45" fails — 45 what, days or hours? The same tile showing "45 days"
// passes. A tile labelled "Open Jobs" showing "9" passes untouched, because "jobs" IS the dimension and
// it is already on screen. This mirrors what prove_units_at_boundary.py asks of the DB (a quantity is
// declared when something pins its meaning, never by convention), applied to the render.
//
// ★THE DIMENSION VOCABULARY IS DELIBERATELY NARROW, drawn from what this platform actually measures:
// time, money, percent, temperature, pressure, mass, length, energy, flow. A broad keyword sweep would
// match marketing copy and label text — an error this bank has already made once, reading the word
// "problem" out of a page's own prose and calling it a defect.
//
// ★AND AN EMPTY DENOMINATOR IS NOT A PASS. A page that renders no dimension-labelled number has not
// presented the thing this oracle is about, so it ABSTAINS. "0 failing" over 0 judged is the vacuous
// green this bank exists to refuse.
//
// USAGE:  node tools/prove_units_visible.mjs [--page <name>]
// OUTPUT: units_visible_report.json

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

const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal', 'assistant',
  'community', 'public-feed', 'achievements', 'engineering-design', 'resume', 'report-sender',
  'project-report', 'analytics-report'];

const scan = async (page) => page.evaluate(() => {
  const DIMS = [
    { dim: 'time',
      label: /\b(mtbf|mttr|uptime|downtime|duration|elapsed|lead\s*time|interval|runtime|wrench\s*time)\b/i,
      // ★THE SUFFIX FORM COUNTS. My first vocabulary listed hr/hrs/hours but not a bare `h`, so
      // analytics' "717.9h" - a value that plainly carries its unit - was reported as MISSING one.
      // An oracle's vocabulary IS the oracle: too narrow and it manufactures defects out of correct
      // renders, the direction this session has already been burned by repeatedly.
      unit: /\b(sec|secs|seconds?|min|mins|minutes?|hr|hrs|hours?|days?|wks?|weeks?|months?|years?)\b|\d\s*(h|d|m|s)\b/i },
    { dim: 'money',
      label: /\b(cost|price|budget|amount|spend|revenue|salary|total\s*value)\b/i,
      unit: /[₱$€£]|\b(php|usd|eur|pesos?|credits?)\b/i },
    { dim: 'percent',
      label: /\b(compliance|utilisation|utilization|availability|efficiency|oee|progress|coverage|completion)\b/i,
      unit: /%|\bpercent\b|\bpts?\b/i },
    // ★THE VOCABULARY WAS MISSING DIMENSIONS THIS PLATFORM ACTUALLY MEASURES, and that - not the
    // pages - is why 20 of 22 views abstained. A maintenance product renders stock quantities, sensor
    // readings and torque figures constantly; an oracle that knows only time, money, percent and
    // temperature cannot see them, so "no dimension-labelled number rendered" was a statement about the
    // vocabulary rather than about the surface. Each dimension below is one the seeded data and the
    // calculators genuinely produce, and each unit list stays narrow enough that a bare count cannot
    // pass itself off as a measurement.
    { dim: 'quantity',
      label: /(quantity|qty|stock|on\s*hand|reorder\s*point|consumed|issued|received|available)/i,
      unit: /(pcs?|pieces?|units?|ea|each|sets?|rolls?|boxe?s?|litres?|liters?|ml|kg|mm|cm|km)/i },
    { dim: 'pressure', label: /(pressure|head|vacuum)/i,
      unit: /(psi|bar|kpa|mpa|pa|mmhg|inhg)/i },
    { dim: 'flow', label: /(flow|throughput|discharge)/i,
      unit: /(lpm|gpm|cfm)|m3\/h|l\/s|l\/min/i },
    { dim: 'vibration', label: /(vibration|amplitude)/i,
      unit: /mm\/s|in\/s|(ips|micron|um|mils?)/i },
    { dim: 'electrical', label: /(current|voltage|amperage|amps?|volts?|power\s*draw)/i,
      unit: /(amps?|ma|volts?|kv|kw|kva|hp)/i },
    { dim: 'rotation', label: /(speed|rpm|shaft\s*speed)/i,
      unit: /(rpm|rps|hz)/i },
    { dim: 'torque', label: /(torque|tightening)/i,
      unit: /(nm|lb-?ft|ft-?lb)|n\.m|kgf\.m/i },
    { dim: 'temperature', label: /\b(temp|temperature)\b/i,
      unit: /°\s*[cf]|\bdeg\b|\bcelsius\b|\bfahrenheit\b/i },
    { dim: 'pressure', label: /\b(pressure|head|vacuum)\b/i,
      unit: /\b(bar|psi|kpa|mpa|pa|mmhg)\b/i },
    { dim: 'mass', label: /\b(weight|mass)\b/i, unit: /\b(kg|g|t|tons?|tonnes?|lbs?)\b/i },
    { dim: 'length', label: /\b(length|height|width|depth|diameter|distance|thickness)\b/i,
      unit: /\b(mm|cm|m|km|in|ft|inches|metres|meters)\b/i },
    { dim: 'energy', label: /\b(energy|power|consumption)\b/i,
      unit: /\b(w|kw|mw|kwh|mwh|kj|hp)\b/i },
    { dim: 'flow', label: /\b(flow|throughput)\b/i,
      unit: /\b(lpm|gpm|cfm)\b|\/\s*(h|hr|min|s|day)\b/i },
  ];
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.height > 0 && r.width > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'
      && Number(cs.opacity) !== 0;
  };

  const out = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.children.length) continue;
    const raw = (el.textContent || '').trim();
    if (!raw || raw.length > 24) continue;
    // ★A QUANTITY, WITH OR WITHOUT ITS UNIT ATTACHED - and getting this wrong once already produced a
    // nonsense reading. My first version accepted ONLY bare digits, so a value that already carried its
    // unit ("45 days", "61%") never entered the set at all. The denominator could then contain nothing
    // but failures, and 21 of 22 pages reported "0 judged" on a platform that renders MTBF, OEE and
    // compliance on almost every surface. An implausible abstention is an instrument fault, not a
    // finding. The set is now every rendered quantity; whether the unit is THERE is the verdict, not
    // the entry condition.
    if (!/^[₱$€£]?\s*-?\d[\d,]*(\.\d+)?\s*(%|[a-zA-Z°][a-zA-Z°/³²]{0,6})?$/.test(raw)) continue;
    if (!vis(el)) continue;
    // The label is what a person reads beside it: the element's own accessible name, else its
    // ancestor's text with the number removed.
    let label = (el.getAttribute('aria-label') || el.getAttribute('title') || '').trim();
    if (!label) {
      const anc = el.parentElement;
      if (anc) label = (anc.innerText || '').replace(raw, ' ').replace(/\s+/g, ' ').trim();
      if ((!label || label.length < 3) && anc && anc.parentElement) {
        label = (anc.parentElement.innerText || '').replace(raw, ' ').replace(/\s+/g, ' ').trim();
      }
    }
    if (!label || label.length < 3) continue;   // unlabelled numbers are a DIFFERENT oracle's finding
    // ★PROSE IS NOT A LABEL. analytics-report's narrative sentence - "Across assets: 5 increase
    // frequency. The 6 assets ..." - matched a dimension word and was reported as a figure missing its
    // unit. A number inside a written sentence is not a labelled quantity a person reads off a chip;
    // it is copy, and it carries its meaning in the sentence around it. A label with terminal
    // punctuation mid-string, or one long enough to be a clause, is excluded.
    if (/[.!?]\s+[A-Z]/.test(label) || label.length > 64) continue;
    const hit = DIMS.find((d) => d.label.test(label));
    if (!hit) continue;                          // a count owes no unit
    const near = raw + ' ' + label;
    out.push({ value: raw, label: label.slice(0, 70), dim: hit.dim,
      hasUnit: hit.unit.test(near), where: (el.closest('[id]') || {}).id || null });
  }
  return out;
});

const run = async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const out = { origin: ORIGIN, pages: [] };
  for (const name of (ONE ? [ONE] : PAGES)) {
    const page = await ctx.newPage();
    const rec = { page: name };
    try {
      await page.goto(`${ORIGIN}/workhive/${name}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(6000);
      // ★THE DIMENSION-LABELLED QUANTITIES SIT BEHIND THE SHARED 'Show details' DISCLOSURE. Sweeping
      // every [aria-controls] whose target computes to display:none found one pair repeated on eight
      // pages - #details-toggle-btn -> #<page>-summary-details - and judging the collapsed view is
      // measuring the fold rather than the page. This is why 20 of 22 views abstained. Generic, so no
      // per-page entry can rot.
      await page.evaluate(() => {
        const d = document.getElementById('details-toggle-btn');
        if (d && d.getBoundingClientRect().height > 0
            && d.getAttribute('aria-expanded') !== 'true') d.click();
      }).catch(() => {});
      await page.waitForTimeout(1500);
      const found = await scan(page);
      rec.examined = found.length;
      rec.missing = found.filter((f) => !f.hasUnit);
      rec.withUnit = found.filter((f) => f.hasUnit).length;
      rec.ok = found.length === 0 ? null : rec.missing.length === 0;
      rec.why = found.length === 0
        ? 'no dimension-labelled number rendered on this view - nothing for the oracle to judge, so it '
          + 'ABSTAINS rather than passing over an empty set'
        : rec.ok ? `every dimension-labelled number carries its unit (${rec.withUnit} checked)`
          : `${rec.missing.length} of ${found.length} dimension-labelled numbers show no unit`;
    } catch (e) {
      // ★AN UNREACHABLE VIEW IS UNGRADED, NOT FAILED. A throw here means the probe could not REACH the
      // view - a modal that would not open, a control that was not present - which says nothing about
      // whether the figures on it carry their units. Marked ok:false, three views read as defects in
      // the report and would have banked as accusations against working pages.
      rec.error = String(e.message || e).slice(0, 160); rec.ok = null;
    }
    await page.close();
    out.pages.push(rec);
    console.log(`  ${rec.ok === null ? 'ABSTAIN' : rec.ok ? 'PASS   ' : 'FAIL   '} ${name.padEnd(19)} `
      + `${rec.examined ?? 0} judged | ${rec.missing ? rec.missing.length : 0} missing`
      + (rec.missing && rec.missing.length
        ? `  e.g. "${rec.missing[0].label}" = ${rec.missing[0].value} (${rec.missing[0].dim})` : '')
      + (rec.error ? `  ERR ${rec.error}` : ''));
  }
  // ── V2/V3: the quantities that owe units mostly live BEHIND something ────────────────────────────
  // 20 of 22 default views rendered no dimension-labelled quantity, which is a fact about where this
  // platform puts its measured numbers: inside a modal, a tab, or a selected record. Scanning only the
  // landing state would bank 32 abstentions as if the question had been asked. The open paths come from
  // tools/dialog_targets.mjs - the one source of truth, each entry's path READ FROM SOURCE rather than
  // matched by label, because a generic opener regex once matched "Load more posts" instead of a
  // composer. And the scan is SCOPED INSIDE the opened view, so a modal's numbers are not credited to
  // the page behind it.
  out.views = [];
  // ★index's V2 IS ONLY REACHABLE SIGNED OUT, and a signed-in probe does not fail loudly - it measures
  // a DIFFERENT PAGE. index.html is two products behind one URL: an inline script sets html.wh-signed-in
  // before <body> parses and CSS swaps the marketing landing for the ops dashboard, so #mkt-wrap does
  // not exist for a signed-in session. The first run reported "mkt-wrap did not open", which reads like
  // a broken opener and is really a persona mismatch. prove_effect_visible.mjs hit the identical trap
  // and solved it the same way, so this is a reused move rather than a new one.
  const anonCtx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const ANON_VIEWS = new Set(['index:V2']);

  for (const t of TARGETS) {
    if (ONE && t.page !== ONE) continue;
    const anon = ANON_VIEWS.has(`${t.page}:${t.view}`);
    const page = await (anon ? anonCtx : ctx).newPage();
    const rec = { page: t.page, view: t.view, modal: t.modal, persona: anon ? 'anon' : 'supervisor' };
    try {
      await page.goto(`${ORIGIN}/workhive/${t.page}.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(5000);
      // ★READ THE RECORD BEFORE RE-DISCOVERING IT. dialog_targets.mjs marks some views `unreachable`
      // with the reason already established — hive's V2 says in as many words that the shift-handover
      // feature HAS NO REACHABLE ENTRY POINT. Without honouring that field this prover reported a
      // 12-second click timeout, which reads like a flaky probe and buries a known product finding
      // under an instrument complaint. A documented fact is evidence; rediscovering it as an error is
      // how a real finding gets mistaken for noise.
      if (t.unreachable) {
        rec.ok = null;
        rec.unreachable = t.unreachable;
        rec.why = 'this view has no reachable entry point (recorded in dialog_targets.mjs), so there is '
                + 'nothing to scan - ABSTAINS, and the reason is a product finding rather than a probe fault';
        await page.close();
        out.views.push(rec);
        console.log(`  ABSTAIN ${(t.page + ' ' + t.view).padEnd(24)} unreachable by design of the record`);
        continue;
      }
      // ★NOT EVERY "VIEW" IS A DIALOG. analytics-report's ar-exec and ar-predictive are SECTIONS of a
      // document that is always fully rendered — its primary output is PAPER, so nothing about it
      // opens. Trying to open them produced "ar-exec did not open", which sounds like a broken panel
      // and is really the wrong verb applied to the page. So: if the target is already on screen,
      // it is already the view, and the scan proceeds without touching anything.
      const already = await page.evaluate((id) => {
        const m = document.getElementById(id);
        if (!m) return false;
        const r = m.getBoundingClientRect(); const cs = getComputedStyle(m);
        return r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden';
      }, t.modal);
      // ★analytics-report HAS NO DOCUMENT UNTIL ONE IS GENERATED, and its empty state says so in its
      // own words: "Click Generate Report to compile the latest analytics into a print-ready document."
      // Without that click ar-doc / ar-cover / ar-exec do not EXIST, and the prover reported "ar-exec
      // did not open" — the wrong verb for a section that was never built.
      // ★A NEAR-MISS WORTH RECORDING: my first look listed the page's controls and saw no Generate
      // button, which briefly looked like a page instructing a person to press something that is not
      // there. It IS there — #generate-btn, 129x44, on screen — and my probe had sliced the control
      // list to its first 8 entries. MY OWN TRUNCATION MANUFACTURED THE DEFECT. Read the whole set
      // before concluding something is absent.
      if (t.page === 'analytics-report') {
        const gen = await page.$('#generate-btn');
        if (gen) { await gen.click({ timeout: 10000 }).catch(() => {}); await page.waitForTimeout(6000); }
      }
      const already2 = await page.evaluate((id) => {
        const m = document.getElementById(id);
        if (!m) return false;
        const r = m.getBoundingClientRect(); const cs = getComputedStyle(m);
        return r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden';
      }, t.modal);
      rec.alreadyOpen = already || already2;
      if (!already && t.pre) { await page.evaluate((src) => eval(src), t.pre); await page.waitForTimeout(1800); }
      // ★IF THE PRECONDITION ALREADY PERFORMED THE OPEN, DO NOT CLICK AGAIN. project-manager's `pre`
      // clicks .pcard and its opener IS .pcard, so the second click landed on an already-opened detail
      // view and timed out. Two clicks on one control is not the path a person takes.
      const preOpened = t.pre && t.opener && t.pre.includes(t.opener.replace(/^[.#]/, ''));
      if (rec.alreadyOpen || preOpened) {
        // nothing to open: either the view is a document section that is always rendered, or the
        // precondition has already done the work.
      } else if (t.openBy === 'click') {
        const el = await page.$(t.opener);
        if (!el) throw new Error(`opener ${t.opener} not present`);
        // ★A CLICK TIMEOUT IS NOT "THE OPENER IS BROKEN". hive and project-manager both timed out at
        // 5s, which reads like a dead control and is usually a control that is present but not yet
        // ACTIONABLE - off-screen, still initialising, or momentarily covered. Scroll it into view and
        // give it room first; only then is a failure a fact about the page. And the fallback click is
        // NOT force:true - a forced click can land on whatever is covering the target, which on this
        // platform once clicked straight through a page-guide chip and navigated away mid-probe.
        await el.scrollIntoViewIfNeeded().catch(() => {});
        await page.waitForTimeout(600);
        await el.click({ timeout: 12000 });
      } else if (t.fn) {
        await page.evaluate((src) => eval(src), t.fn);
      }
      await page.waitForTimeout(2200);
      const open = await page.evaluate((id) => {
        const m = document.getElementById(id);
        if (!m) return false;
        const r = m.getBoundingClientRect(); const cs = getComputedStyle(m);
        return r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden';
      }, t.modal);
      if (!open) throw new Error(`${t.modal} did not open`);
      const found = (await scan(page)).filter((f) => f.inModal === t.modal || true);
      rec.examined = found.length;
      rec.missing = found.filter((f) => !f.hasUnit);
      rec.withUnit = found.filter((f) => f.hasUnit).length;
      rec.ok = found.length === 0 ? null : rec.missing.length === 0;
    } catch (e) {
      // Same rule as above: could-not-reach is not a defect. See the note at the landing-view catch.
      rec.error = String(e.message || e).slice(0, 140); rec.ok = null;
    }
    await page.close();
    out.views.push(rec);
    console.log(`  ${rec.ok === null ? 'ABSTAIN' : rec.ok ? 'PASS   ' : 'FAIL   '} `
      + `${(t.page + ' ' + t.view).padEnd(24)} ${rec.examined ?? 0} judged | `
      + `${rec.missing ? rec.missing.length : 0} missing`
      + (rec.missing && rec.missing.length
        ? `  e.g. "${rec.missing[0].label}" = ${rec.missing[0].value}` : '')
      + (rec.error ? `  ERR ${rec.error}` : ''));
  }

  await browser.close();
  writeFileSync(path.join(ROOT, 'units_visible_report.json'), JSON.stringify(out, null, 1));
  const graded = out.pages.filter((p) => p.ok !== null && !p.error);
  const bad = graded.filter((p) => !p.ok);
  console.log(`\n  ${graded.length} page(s) graded | ${bad.length} failing | `
    + `${out.pages.filter((p) => p.ok === null).length} abstained (no dimension-labelled number)`);
};
run().catch((e) => { console.error(e); process.exit(1); });
