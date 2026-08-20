// prove_number_explained.mjs — the CE `number_explained` oracle, measured on the rendered page.
//
// THE ORACLE: "a person can say what the number MEANS without leaving the surface."
//
// ★NAMING IS NOT EXPLAINING, and that distinction is the whole reason this is a separate prover from
// prove_number_labelled.mjs. That one asks whether something adjacent NAMES the figure ("MTBF", "PM
// compliance") and the roster passes it 79/79. This one asks the harder question: can a person say what
// the number MEANS? "PM compliance 61%" is named and unexplained — 61% of WHAT, over WHAT window,
// counted HOW? A label that names a metric a person cannot decompose is a vibe with a number attached.
//
// ★ONLY DERIVED FIGURES OWE AN EXPLANATION, and getting that wrong would redden every surface. A raw
// COUNT explains itself: "Open Jobs 9" is nine jobs, and there is nothing to decompose. A PERCENTAGE, a
// RATE, a SCORE, an INDEX or a COMPOSITE is computed from things the reader cannot see — that is where
// the meaning lives off-screen. So the set is derived figures only, and a page with none ABSTAINS.
//
// ★WHAT COUNTS AS AN EXPLANATION, drawn from what this platform already does well rather than invented:
//   · a DENOMINATOR — "/", "of 30", "out of", "N of M"
//   · a WINDOW — "last 30 days", "30d", "this shift", "today", "per month"
//   · a DERIVATION — "based on", "computed from", "excludes", "counted once per", "weighted by"
//   · a DEFINITION — the metric expanded ("completed on time / scheduled")
// Any ONE of those, within the figure's own card or section, discharges the obligation. Requiring all
// four would fail good surfaces; requiring none would pass every surface.
//
// ★AND THE SCOPE IS THE FIGURE'S OWN BLOCK, not the page. A body-wide keyword sweep would match this
// platform's marketing copy and its own guide text — an error this bank has made and recorded. The
// search climbs at most to the enclosing card/section, which is where a person actually looks.
//
// USAGE:  node tools/prove_number_explained.mjs [--page <name>]
// OUTPUT: number_explained_report.json

import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'node:url';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal', 'assistant',
  'community', 'public-feed', 'achievements', 'engineering-design', 'resume', 'report-sender',
  'project-report', 'analytics-report'];

const scan = async (page) => page.evaluate(() => {
  // A DERIVED figure: its label names a computed quantity, or the value itself is a percentage.
  const DERIVED = /\b(compliance|utilisation|utilization|availability|efficiency|oee|readiness|score|index|composite|rate|mtbf|mttr|percentile|progress|coverage|confidence|rpn|beta|eta)\b/i;
  const EXPLAINED = [
    // ★`/100` ALONE IS A DENOMINATOR and my first pattern missed it, failing hive's "HEALTHY /100
    // composite risk · lower is better" — a figure that states its scale AND its direction, which is
    // better than most on this roster. Requiring a digit on BOTH sides of the slash was the error.
    // An oracle's vocabulary IS the oracle: too narrow and it manufactures defects out of good work.
    // ★AND `\d+\b` CANNOT MATCH "8h", which failed the very fix I had just shipped. After adding
    // "0.0h / 8h" to dayplanner's capacity bar — the denominator now plainly on screen — this pattern
    // still reported it unexplained, because `8` and `h` are both word characters so there is no word
    // boundary between them for `\b` to find. Two regex faults in one oracle, both mine, both in the
    // direction of failing a surface that was doing the right thing. The trailing boundary is gone.
    { kind: 'denominator', re: /\b\d+(\.\d+)?\s*\w*\s*(of|\/)\s*\d+|\/\s*\d+|\bout of\b|\bper\b/i },
    { kind: 'window', re: /\b(last|past)\s+\d+\s*(d|days?|weeks?|months?)\b|\b\d+\s*d\b|\bthis (shift|week|month|day)\b|\btoday\b|\brolling\b/i },
    { kind: 'derivation', re: /\b(based on|computed|calculated|derived|excludes?|includes?|counted|weighted|threshold|formula|inputs?)\b/i },
    { kind: 'definition', re: /\b(completed|scheduled|on[- ]time|failures?|operating time|repair time)\b/i },
    // ★A CITED STANDARD IS THE STRONGEST DEFINITION A MAINTENANCE METRIC CAN CARRY, and leaving it
    // out of this vocabulary failed analytics' availability figures — labelled "AVAILABILITY % ISO
    // 14224:2016 §9.2", which names not just the standard but the CLAUSE defining the computation.
    // This bank's own domain-truth oracles demand exactly that ("the governing standard is named per
    // calc"), so an oracle scoring it unexplained is arguing with its own roadmap. The clause matters:
    // "ISO 14224" alone is a badge, "§9.2" is a pointer someone can follow.
    // A DOTTED METRIC NUMBER IS ITSELF THE CLAUSE. I required a separate section marker on the
    // reasoning that "ISO 14224" alone is a badge while "s9.2" is a pointer - true, but
    // "SMRP Metric 2.1.1" carries the pointer INSIDE the number, and demanding a section sign
    // beside it rejected a citation that is every bit as followable. Either form qualifies.
    { kind: 'standard', re: /(ISO|IEC|API|NFPA|ASME|ASTM|SMRP|EN)\s?(?:metric|standard|std|part)?\s?\d{1,5}(?:\.\d+)+|(ISO|IEC|API|NFPA|ASME|ASTM|SMRP|EN)\s?\d{3,5}(:\d{4})?(?:[^A-Za-z0-9]).{0,24}(§|sec(?:tion)?|cl(?:ause)?\.?)\s?\d/i },
  ];
  const vis = (el) => {
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.height > 0 && r.width > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'
      && Number(cs.opacity) !== 0;
  };
  // The block a person reads: the enclosing card/section, never the whole page.
  const SEL = '.simple-card, .wh-card, .section-card, .oh-card, .kpi, .card, '
    + '[class*="card"], [class*="tile"], section, article';
  // ★A `[class*="card"]` MATCH CAN LAND ON AN INNER WRAPPER, and that manufactured a false finding
  // against project-manager. Its project card carries the denominator plainly — "📋 6/10" — but the
  // percentage sits inside `.pcard-FOOT`, whose class also contains "card", so `closest()` stopped
  // there and saw only the status pill: label "active", value "25%", reported as unexplained. The card
  // was explaining itself one div up. So climb while the block is too small to be the thing a person
  // reads as a unit, and stop at the outermost card-like ancestor.
  // ★A BLOCK HOLDING MANY FIGURES IS A LIST, NOT ONE FIGURE'S CONTEXT — and that manufactured this
  // oracle's only failure. analytics renders a per-asset availability list; the enclosing block resolved
  // to the whole list, so each percentage's "label" became the OTHER rows' text
  // ("CT-001 LATH-001 93.5% CR-001 95.8% ..."), and nine figures were reported as named-but-unexplained
  // on the strength of a label that is not a label. The context of a figure is the smallest block that
  // contains THAT figure and no other, so the climb stops before a second one is swallowed.
  const numLeaves = (b) => [...b.querySelectorAll('*')].filter((n) => !n.children.length
    && /^[₱$€£]?\s*-?\d[\d,]*(\.\d+)?\s*%?$/.test((n.textContent || '').trim())).length;
  const blockOf = (el) => {
    let b = el.closest(SEL) || el.parentElement;
    if (b && numLeaves(b) > 1) {
      // Already too coarse: walk back DOWN toward the figure until the block owns it alone.
      let d = el.parentElement;
      while (d && d !== b && numLeaves(d) > 1) d = d.parentElement;
      let up = el.parentElement;
      while (up && up !== b && numLeaves(up) <= 1
             && (up.innerText || '').replace(/\s+/g, ' ').trim().length < 40) up = up.parentElement;
      b = (up && numLeaves(up) <= 1) ? up : (el.parentElement || b);
    }
    for (let i = 0; i < 3 && b; i++) {
      const txt = (b.innerText || '').replace(/\s+/g, ' ').trim();
      if (txt.length > 40) break;              // big enough to be a labelled figure in context
      const up = b.parentElement && b.parentElement.closest(SEL);
      if (!up || up === b || numLeaves(up) > 1) break;   // never climb into a list
      b = up;
    }
    return b;
  };

  const out = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.children.length) continue;
    const raw = (el.textContent || '').trim();
    if (!raw || raw.length > 24) continue;
    if (!/^[₱$€£]?\s*-?\d[\d,]*(\.\d+)?\s*%?$/.test(raw)) continue;
    if (!vis(el)) continue;
    const block = blockOf(el);
    if (!block) continue;
    const blockText = (block.innerText || '').replace(/\s+/g, ' ').trim();
    const label = blockText.replace(raw, ' ').replace(/\s+/g, ' ').trim();
    const isPct = /%$/.test(raw);
    if (!isPct && !DERIVED.test(label)) continue;      // a raw count explains itself
    if (label.length < 3) continue;                    // unlabelled is a DIFFERENT oracle's finding
    // ★ADJACENCY IS NOT A WHOLE SECTION, and ignoring that manufactured three findings. On
    // project-report the enclosing block resolved to #progress-section — a TABLE — so every cell in it
    // inherited the section's derived-ness, and a progress-log row's "4.0 hours" was reported as an
    // unexplained metric labelled "Replace mechanical seal + bearings Leandro Mar…". A figure a person
    // reads WITH its explanation beside it has a short label; several hundred characters of table is
    // not adjacency, it is a different question (whether a table's columns are headed).
    if (label.length > 140) continue;
    // A cell inside a data table is a datum, not a KPI with an explanation next to it.
    if (el.closest('td, th, tr, table')) continue;
    // A ROW IN A LIST IS EXPLAINED BY THE LIST'S HEADER, which a person reads once rather than on every
    // line. analytics renders per-asset availability as rows labelled only by their asset code
    // ("CT-001", "LATH-001"), while the section above them says "AVAILABILITY % ISO 14224:2016 s9.2 ...
    // MTBF/(MTBF+MTTR)". Demanding that each row repeat the standard would be asking the product to be
    // worse. So the nearest heading inside the enclosing section joins the label for the test - it is
    // still adjacency, just the adjacency a reader actually uses.
    // ★AND THE SECTION HAS TO BE THE ONE THAT OWNS THE FIGURE, which on analytics is the identified KPI
    // container (#kpi-0). All five remaining bare rows sat inside it, alongside the very sentence that
    // explains them - "AVAILABILITY % ISO 14224:2016 s9.2 ... MTBF/(MTBF+MTTR)" - while `closest` on the
    // card/panel classes stopped at a smaller inner wrapper that carries no citation. An identified
    // container is the unit a page author treats as one thing, so it is tried when the class-based
    // ancestor turns up no explanation.
    const sect = block.closest('section, article, .card, [class*="card"], [class*="panel"]')
      || block.closest('[id]') || block.parentElement;
    // ★THIS PLATFORM PUTS ITS STANDARD CITATION IN A BARE <small>, NOT IN A HEADING. Probed live:
    // analytics' availability card explains itself with "ISO 14224:2016 - Counts calendar days between
    // failures, not ..." inside a <small> in the same .simple-card, and the AVAILABILITY wording is
    // uppercased by CSS, which is why grepping the source for "AVAILABILITY %" found nothing. A heading-
    // only selector cannot see the sentence the product actually wrote, so the explanation is looked for
    // wherever this codebase puts it: headings, and the small/sub/note/caption line beneath a figure.
    const hdrEl = sect && sect.querySelector('h1, h2, h3, h4, [class*="title"], [class*="heading"], '
      + 'small, [class*="-sub"], [class*="note"], [class*="caption"], [class*="footnote"]');
    let hdr = hdrEl ? (hdrEl.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 120) : '';
    // The class-based ancestor wins when it explains the figure, but `closest` stops at the FIRST match
    // and on analytics that is an inner wrapper carrying no citation - so when it yields nothing, the
    // identified container (#kpi-0) is asked instead. Falling back only on an empty result keeps the
    // tighter scope preferred, rather than letting a big container explain a figure it merely contains.
    // ★CLIMB UNTIL AN ANCESTOR ACTUALLY EXPLAINS - the general rule that subsumes three special cases
    // I tried first. #kpi-0 turned out to be a DISCLOSURE PANEL (.kpi-detail) holding 62 asset/percentage
    // leaves and no citation at all; the sentence that explains them ("AVAILABILITY % ISO 14224:2016
    // s9.2 ... MTBF/(MTBF+MTTR)") lives in the KPI CARD that owns the panel. Fixing that by naming
    // another selector would just move the guess up one level. A figure is explained if ANY enclosing
    // block explains it, because that is how a person reads: the column header is above the rows, the
    // card header is above the column. Bounded to 5 levels so a page-wide banner cannot explain
    // everything on the page by containing one standard reference.
    const HDR_SEL = 'h1, h2, h3, h4, [class*="title"], [class*="heading"], small, [class*="-sub"], '
      + '[class*="note"], [class*="caption"], [class*="footnote"]';
    if (!EXPLAINED.some((e) => e.re.test(hdr))) {
      let up = block.parentElement;
      for (let lvl = 0; lvl < 5 && up && up !== document.body && !hdr; lvl++) {
        const t = [...up.querySelectorAll(HDR_SEL)]
          .map((c) => (c.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 160))
          .find((x) => x && EXPLAINED.some((e) => e.re.test(x)));
        if (t) hdr = t;
        up = up.parentElement;
      }
    }
    const found = EXPLAINED.filter((e) => e.re.test(label) || (hdr && e.re.test(hdr))).map((e) => e.kind);
    out.push({ value: raw, label: label.slice(0, 90), explained: found.length > 0, by: found,
      where: (el.closest('[id]') || {}).id || null });
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
      // ★THE DERIVED FIGURES ARE NOT ALWAYS ON THE LANDING VIEW, and judging only that view produced
      // EIGHTEEN abstentions — implausible on a platform that renders OEE, MTBF and PM compliance.
      // An implausible abstention is an instrument fault, not a finding: analytics' landing state shows
      // only connection-widget numbers, while its KPI heroes live behind the phase panels. This is the
      // same trap the units prover hit, so the fix is the same — reach the view that owns the metric.
      const REACH = {
        analytics: "if (typeof setPhase === 'function') setPhase('descriptive');",
        'analytics-report': "var b=document.getElementById('generate-btn'); if(b) b.click();",
        'engineering-design': "var t=[...document.querySelectorAll('[data-tab]')].find(function(e){return e.dataset.tab==='history';}); if(t) t.click();",
        // ★THE DERIVED FIGURES ON THIS PLATFORM MOSTLY LIVE BEHIND A TAB, which is why 17 pages abstained
        // on their landing view. asset-hub is the clearest case: its RPN (S x O x D) and its Weibull beta
        // and eta are exactly the "computed from things the reader cannot see" figures this oracle exists
        // for, and none of them render until the tab is opened. Reaching them asks the question of the
        // view that actually owns the metric, the same fix prove_units_visible needed.
        // ★AND THE TAB IS STATE-GATED: measured, all three of asset-hub's tabs (fmea/weibull/pf) report
        // height 0 until an ASSET IS SELECTED, so clicking one on the landing view does nothing and the
        // page keeps abstaining. Select a node first, then open the tab - the same precondition shape
        // dialog_targets.mjs already records for pm-scheduler's edit control. The node selector is
        // [data-node-id] - probed, 25 present; the guessed .asset-node / [onclick*=selectAsset]
        // forms match ZERO elements, which is how a REACH step can look right and do nothing.
        // ★AND THE GATE IS A DISCLOSURE, NOT THE SELECTION: walking the tab's ancestors live showed
        // #reliability-card (.section-card) sitting at display:none, revealed by #asset-view-toggle
        // ('Show Reliability Workbench (engineer view)'). Selecting a node alone never opens it, which
        // is why three selector guesses in a row changed nothing - the missing step was a PRESS.
        'asset-hub': "var w=document.getElementById('asset-view-toggle'); if(w) w.click(); var n=document.querySelector('[data-node-id]'); if(n) n.click(); setTimeout(function(){var t=[...document.querySelectorAll('[data-tab]')].find(function(e){return e.dataset.tab==='weibull';}); if(t) t.click();}, 1500);",
        skillmatrix: "var b=document.querySelector('.skill-cell, [class*=\"skill-cell\"]'); if(b) b.click();",
      };
      const QUERY = { 'project-report': '?project_id=539e0d9a-9ff7-474b-ab03-9254406ca7dc' };
      await page.goto(`${ORIGIN}/workhive/${name}.html${QUERY[name] || ''}`,
        { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(6000);
      // ★ONE SHARED DISCLOSURE HIDES DERIVED FIGURES ON EIGHT PAGES. Sweeping every [aria-controls]
      // whose target computes to display:none found the same pair on hive, inventory, pm-scheduler,
      // skillmatrix, shift-brain, achievements, report-sender and alert-hub: #details-toggle-btn ->
      // #<page>-summary-details, labelled "Show details". That is where the explained figures live, and
      // judging the collapsed view was measuring the fold rather than the page. Opening it is generic,
      // so it costs no per-page REACH entry and cannot rot when a page is renamed.
      await page.evaluate(() => {
        const d = document.getElementById('details-toggle-btn');
        if (d && d.getBoundingClientRect().height > 0
            && d.getAttribute('aria-expanded') !== 'true') d.click();
      }).catch(() => {});
      await page.waitForTimeout(1500);
      if (REACH[name]) {
        await page.evaluate((src) => eval(src), REACH[name]).catch(() => {});
        rec.reached = true;
        // ★A REPORT STILL GENERATING HAS NO FIGURES TO JUDGE, and abstaining on it records the wait
        // rather than the page. analytics-report builds its whole body after the press and returned
        // derived=0 at 6s having previously rendered 4 - an abstention that is really a timeout. Wait
        // for a figure to actually appear, then settle; fall through on timeout so a page that renders
        // none still abstains honestly.
        await page.waitForFunction(() => [...document.querySelectorAll('*')].some((el) =>
          !el.children.length && /^\s*-?\d[\d,]*(\.\d+)?\s*%?\s*$/.test(el.textContent || '')),
          { timeout: 20000 }).catch(() => {});
        await page.waitForTimeout(6000);
      }
      const found = await scan(page);
      rec.derived = found.length;
      rec.explained = found.filter((f) => f.explained).length;
      rec.bare = found.filter((f) => !f.explained).slice(0, 5);
      // ★A PAGE WITH NO DERIVED FIGURE ABSTAINS. "0 unexplained of 0" reads identically to a thorough
      // pass, which is the vacuous green this bank refuses.
      rec.ok = found.length === 0 ? null : rec.bare.length === 0;
      rec.why = found.length === 0
        ? 'no derived figure rendered on this view - a raw count explains itself, so there is nothing '
          + 'for this oracle to judge; ABSTAINS rather than passing over an empty set'
        : rec.ok ? `every derived figure carries a denominator, window, derivation or definition (${rec.explained} judged)`
          : `${rec.bare.length} of ${found.length} derived figures are NAMED but not EXPLAINED`;
    } catch (e) { rec.error = String(e.message || e).slice(0, 160); rec.ok = false; }
    await page.close();
    out.pages.push(rec);
    console.log(`  ${rec.ok === null ? 'ABSTAIN' : rec.ok ? 'PASS   ' : 'FAIL   '} ${name.padEnd(19)} `
      + `derived=${rec.derived ?? 0} explained=${rec.explained ?? 0} bare=${rec.bare ? rec.bare.length : 0}`
      + (rec.bare && rec.bare.length ? `  e.g. "${rec.bare[0].label.slice(0, 46)}" = ${rec.bare[0].value}` : '')
      + (rec.error ? `  ERR ${rec.error}` : ''));
  }
  await browser.close();
  writeFileSync(path.join(ROOT, 'number_explained_report.json'), JSON.stringify(out, null, 1));
  const graded = out.pages.filter((p) => p.ok !== null && !p.error);
  console.log(`\n  ${graded.length} graded | ${graded.filter((p) => !p.ok).length} failing | `
    + `${out.pages.filter((p) => p.ok === null).length} abstained (no derived figure)`);
};
run().catch((e) => { console.error(e); process.exit(1); });
