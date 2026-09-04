// prove_jargon_is_glossed.mjs — T177: a worker must not meet an unexplained domain acronym.
//
// THE ORACLE: for every domain acronym a page actually RENDERS, that page must also gloss it —
// an expansion in parentheses, a dash/colon definition, an <abbr>, or a title attribute. A term
// the platform shows and never explains is a word the reader has to already know, and this
// platform's audience explicitly includes new graduates and non-technicians.
//
// ★SOURCE SCANNING CANNOT ANSWER THIS. A grep finds "MTBF" in a <script> string, a CSS class, a
// comment, and a template that never renders. What matters is what a person READS, so this walks
// signed in and reads innerText.
//
// ★AND IT IS A STANDALONE FILE FOR A MEASURED REASON. The first attempt was assembled through a
// shell heredoc, so its word-boundary escapes crossed four layers (bash -> file -> JS string ->
// RegExp) and arrived corrupted: it reported two bare terms on analytics.html while a follow-up
// that should have printed their surrounding sentences found NEITHER term at all. A detector and
// its own follow-up disagreeing about whether a string exists means neither reading is evidence,
// so nothing was banked. Every pattern here is a literal in this file, built with RegExp source
// strings that no shell ever touches.
//
// Usage:  node tools/prove_jargon_is_glossed.mjs [--page <file>]
// Exit 0 always: this is a RECORDER (see tools/read_recorder_findings.py) — a term being bare is a
// judgement call about audience, not a build-breaking defect, and gating it would invite
// suppression rather than glossing.
import { writeFileSync } from 'fs';
import { chromium } from '@playwright/test';
import { signIn, SEEDER } from './live_page_journeys.mjs';

const args = process.argv.slice(2);
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// ★EACH PAGE CARRIES A SETTLE FLOOR, AND FALLING BELOW IT IS UNGRADED - NEVER CLEAN.
// A run of this census reported 0 bare terms on all 8 pages while pm-scheduler rendered 872 visible
// characters against the 2,561 an earlier walk measured, and asset-hub 956 against 3,132. A heavy
// board run was saturating the local stack, so the settle caught partial renders and the census
// read an under-loaded page as an explained one - a term cannot be found bare on text that never
// arrived. The floors below are ~40% of each page's measured healthy count: low enough not to
// trip on ordinary variance, high enough that a half-rendered page cannot pass as clean.
// Measuring while a board runs produces false cleans; this makes the prover say so instead.
//
// ★AND SOME TERMS ARE NOT AT REST. The overloaded words live where the work happens, not on the
// landing state: pm-scheduler renders "Deferred" in a completion history, marketplace shows
// "reservation" once a listing draft exists. A resting census reports them ABSENT, which reads
// identically to "present and explained" - the same at-rest ceiling prove_at_cap_fits had to drive
// past to reach 56 of 66 capped fields. `open` runs in the page before the read; a flow that fails
// to open is reported, never silently skipped.
const PAGES = [
  { page: 'index.html',        floor: 400 },
  { page: 'analytics.html',    floor: 1700 },
  // ★THE MARK-DONE CONTROL DOES NOT EXIST ON THE BARE PAGE. pm-scheduler reaches its scope items
  // through an ?asset= arrival - the same hop alert-hub hands it, and the same one
  // prove_flow_fits_the_floor already documents. Without the query the resting page has no
  // completion sheet to open, so the census reported [no mark-done control] and 'Deferred' stayed
  // unmeasured. A paramless walk is a different page.
  { page: 'pm-scheduler.html', floor: 1000,
    query: '?asset=' + encodeURIComponent('Amada HFE 80-25'),
    open: `(() => { const b = document.querySelector('[onclick^="markDone("]');
                    if (!b) return 'no mark-done control'; b.click(); return 'completion sheet opened'; })()` },
  { page: 'asset-hub.html',    floor: 1200 },
  { page: 'inventory.html',    floor: 700 },
  { page: 'logbook.html',      floor: 400 },
  { page: 'marketplace.html',  floor: 1700 },
  { page: 'skillmatrix.html',  floor: 400 },

  // ★THE REST OF THE CHROME-BEARING ROSTER, ON A WEAK DEFAULT FLOOR - AND THAT IS A STATED
  // LIMITATION, NOT AN OVERSIGHT. The eight pages above carry floors derived from their MEASURED
  // healthy character counts, so a half-rendered page trips them. These 24 have no baseline yet, so
  // they fall back to DEFAULT_FLOOR, which catches a page that failed outright and will NOT catch a
  // page that rendered 60% of itself. Their reports still record renderedChars, so the honest way to
  // tighten them is to read a few healthy runs and set real floors - never to guess a number now and
  // let it look like evidence. A zero from these pages is weaker than a zero from the first eight,
  // and the report says which is which.
  { page: 'achievements.html' },        { page: 'ai-quality.html' },
  { page: 'alert-hub.html' },           { page: 'analytics-report.html' },
  { page: 'architecture.html' },        { page: 'assistant.html' },
  { page: 'audit-log.html' },           { page: 'community.html' },
  { page: 'dayplanner.html' },          { page: 'engineering-design.html' },
  { page: 'hive.html' },                { page: 'integrations.html' },
  { page: 'marketplace-admin.html' },   { page: 'marketplace-seller-profile.html' },
  { page: 'marketplace-seller.html' },  { page: 'ph-intelligence.html' },
  { page: 'plant-connections.html' },   { page: 'project-manager.html' },
  { page: 'project-report.html' },      { page: 'public-feed.html' },
  { page: 'report-sender.html' },       { page: 'resume.html' },
  { page: 'shift-brain.html' },         { page: 'voice-journal.html' },
];

// Weak on purpose: it separates "the page failed" from "the page rendered", and nothing finer.
const DEFAULT_FLOOR = 300;

// ★USER-WRITTEN TEXT IS NOT PLATFORM COPY, AND THE CENSUS CANNOT TELL BY READING. Widening to 32
// pages produced 11 with bare terms, and FOUR of those were people's own words: community and
// public-feed flagged MTBF and CMMS inside worker POSTS ("what's your MTBF target on critical
// pumps?", "Excel? CMMS? Anything better?"), voice-journal flagged OEE inside a worker's own note
// that literally asks "What is OEE?", and shift-brain flagged LOTO inside seeded job data
// (BF-002 · LOTO · PTW-2026-3875). The platform is not failing to explain a word a WORKER chose to
// type, and a check that demands it would be asking the product to gloss its users - the same
// category error as counting a vendored library's code as your own defect.
// These selectors are subtracted before the read, so the census judges only what the PLATFORM says.
const USER_CONTENT = {
  'community.html':      ['.post-card', '.post-body', '.reply', '#feed', '#posts'],
  'public-feed.html':    ['.post-card', '.post-body', '.feed-item', '#feed', '#posts'],
  'voice-journal.html':  ['#history-list'],
  // shift-brain's LOTO lives in SEEDED JOB DATA (risk/PM/carry/parts lists); its 'deferred'
  // does NOT - that is platform copy explaining the plan, and it must stay in scope.
  'shift-brain.html':    ['#risk-list', '#pms-list', '#carry-list', '#parts-list'],
};

// Acronyms a worker meets on the glass. Each entry carries the expansion we accept as a gloss, so
// the check is "is it explained", never "does the exact word appear".
const TERMS = [
  { t: 'MTBF', expand: 'mean time between failures' },
  { t: 'MTTR', expand: 'mean time to repair' },
  { t: 'OEE',  expand: 'overall equipment effectiveness' },
  { t: 'RCM',  expand: 'reliability-centered maintenance' },
  { t: 'FMEA', expand: 'failure mode' },
  { t: 'RPN',  expand: 'risk priority number' },
  { t: 'LOTO', expand: 'lock-out' },
  { t: 'CMMS', expand: 'maintenance management' },
  { t: 'SOW',  expand: 'scope of work' },
  { t: 'BOM',  expand: 'bill of materials' },
  { t: 'PPE',  expand: 'protective equipment' },
  { t: 'KPI',  expand: 'key performance' },
];

// ★THE HARDER HALF: WORDS A READER ALREADY KNOWS, USED TO MEAN SOMETHING ELSE. An acronym at least
// announces that it is jargon - a reader who does not know MTBF can see that they do not know it.
// These do the opposite. "Reservation" sounds like a booking and means a credit HOLD. "Staging"
// sounds like a phase and means parts pre-picked for a job. "Deferred" sounds like cancelled and
// means the task is still due and still counting as overdue. A reader glides past each of them
// with the wrong meaning and never knows to ask, which makes them more dangerous than an acronym,
// not less.
//
// SCOPED DELIBERATELY: only terms whose DOMAIN meaning departs from the everyday one AND whose
// misreading changes what a person would do. Not "hive" - it is the platform's core noun,
// introduced at onboarding and used on every surface, and demanding a gloss everywhere would be
// noise that gets this check switched off.
// ★EACH TERM CARRIES SEVERAL ACCEPTABLE GLOSSES, BECAUSE A ONE-PHRASE ORACLE REJECTS REAL FIXES.
// This was measured on itself: 'deferred' was written with the single expansion "still due", the
// copy was then fixed to read "the task stays due", and the census went on reporting the term bare
// against a page that now explains it perfectly. An oracle's VOCABULARY is part of the oracle - a
// detector that only accepts the words its author happened to imagine will convict the next good
// fix, and whoever wrote that fix will reasonably conclude the check is broken and stop reading it.
const OVERLOADED = [
  { t: 'reservation', expand: ['hold', 'held'],
    why: 'sounds like a booking; means credits held against a listing' },
  { t: 'staging',     expand: ['pick', 'picked', 'set aside'],
    why: 'sounds like a phase; means parts pre-picked for a job' },
  { t: 'deferred',    expand: ['still due', 'stays due', 'remains due', 'still counts as overdue'],
    why: 'sounds like cancelled; the task is still due and still counts overdue' },
];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await signIn(ctx, 'supervisor');

const results = [];
for (const { page, floor: pageFloor, open, query } of PAGES) {
  const floor = pageFloor || DEFAULT_FLOOR;
  const baselined = pageFloor !== undefined;
  if (ONE && page !== ONE) continue;
  const p = await ctx.newPage();
  await p.goto(`${SEEDER}/workhive/${page}${query || ''}`, { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(9000);
  // drive the flow that exposes the work-time vocabulary, and RECORD whether it opened
  let opened = null;
  if (open) {
    try { opened = await p.evaluate(open); } catch (e) { opened = 'open threw: ' + String(e).slice(0, 60); }
    await p.waitForTimeout(2500);
  }

  const rec = await p.evaluate(({ terms, overloaded, exclude }) => {
    // subtract user-written regions so the census judges only what the PLATFORM says
    let excludedChars = 0;
    const hidden = [];
    for (const sel of (exclude || [])) {
      for (const el of document.querySelectorAll(sel)) {
        excludedChars += (el.innerText || '').length;
        hidden.push([el, el.style.display]);
        el.style.display = 'none';
      }
    }
    const text = (document.body.innerText || '').replace(/\s+/g, ' ');
    for (const [el, prev] of hidden) el.style.display = prev;   // restore, never leave the page altered
    // titles and <abbr> count as a gloss even when the expansion is not in the visible flow
    const aria = Array.from(document.querySelectorAll('[title], abbr, [aria-label]'))
      .map((e) => (e.getAttribute('title') || e.getAttribute('aria-label') || e.textContent || ''))
      .join(' ');
    const haystack = (text + ' ' + aria).toLowerCase();
    const out = { present: [], bare: [] };
    for (const { t, expand } of terms) {
      // built here, in the page, from a plain literal - no shell, no heredoc, no re-escaping
      const word = new RegExp('(^|[^A-Za-z])' + t + '([^A-Za-z]|$)');
      if (!word.test(text)) continue;
      out.present.push(t);
      const glossed = haystack.includes(expand.toLowerCase());
      if (!glossed) out.bare.push(t);
    }
    // the overloaded-word half: same gloss test, reported separately because a bare acronym and a
    // silently-redefined ordinary word are different problems for the reader
    out.renderedChars = text.length;
    out.excludedChars = excludedChars;
    out.excludedRegions = hidden.length;
    out.overloadedPresent = [];
    out.overloadedBare = [];
    for (const { t, expand } of overloaded) {
      const word = new RegExp('(^|[^A-Za-z])' + t + '([^A-Za-z]|$)', 'i');
      if (!word.test(text)) continue;
      out.overloadedPresent.push(t);
      // any ONE of the accepted glosses explains it
      const accepted = Array.isArray(expand) ? expand : [expand];
      if (!accepted.some((e) => haystack.includes(e.toLowerCase()))) out.overloadedBare.push(t);
    }

    // ★a term reported bare must be quotable, or the reading is not evidence
    out.context = {};
    for (const t of out.bare.concat(out.overloadedBare)) {
      const m = text.match(new RegExp('.{0,50}(^|[^A-Za-z])' + t + '([^A-Za-z]|$).{0,50}', 'i'));
      out.context[t] = m ? m[0].trim() : '(NO CONTEXT FOUND - detector disagrees with itself)';
    }
    return out;
  }, { terms: TERMS, overloaded: OVERLOADED, exclude: USER_CONTENT[page] || [] });

  rec.page = page;
  rec.floor = floor;
  rec.baselined = baselined;
  rec.opened = opened;
  results.push(rec);
  const allBare = rec.bare.concat(rec.overloadedBare || []);
  // ★UNDER THE FLOOR IS UNGRADED, NOT CLEAN. A term cannot be found bare on text that never
  // arrived, so a half-rendered page must not be able to report zero findings.
  if (rec.renderedChars < rec.floor) {
    rec.ungraded = `rendered ${rec.renderedChars} chars, below this page's settle floor of ${rec.floor}`;
    console.log(`  UNGRADED ${page.padEnd(22)} ${rec.ungraded} - a partial render cannot be read as clean`);
    await p.close();
    continue;
  }
  const mark = allBare.length ? 'BARE' : 'ok  ';
  const openNote = rec.opened ? `  [${rec.opened}]` : '';
  console.log(`  ${mark} ${page.padEnd(30)}${baselined ? ' ' : '~'}acronyms ${rec.present.length}/${rec.bare.length} bare · ` +
              `overloaded ${(rec.overloadedPresent || []).length}/${(rec.overloadedBare || []).length} bare` +
              (allBare.length ? `  ->  ${allBare.join(', ')}` : '') + openNote);
  for (const t of allBare) console.log(`         ${t}: "${rec.context[t]}"`);
  await p.close();
}
await browser.close();

// A --page probe must not overwrite the full sweep's verdicts: bank_prover_reports.py reads this
// file to bank a whole family, so a one-page run landing on the sweep's filename does not look like
// a truncated report — it looks like a small sweep. Same ternary the other 73 narrowing provers
// use; a full run still writes exactly the same name, so no baseline moves.
writeFileSync(ONE ? 'jargon_glossed_report.partial.json' : 'jargon_glossed_report.json',
  JSON.stringify({ generated_by: 'tools/prove_jargon_is_glossed.mjs', scope: ONE || 'all', results }, null, 2));

const bare = results.filter((r) => r.bare.length || (r.overloadedBare || []).length);
const ungraded = results.filter((r) => r.ungraded);
const rendered = results.reduce((a, r) => a + r.present.length, 0);
console.log(`\n  ${results.length} pages · ${rendered} acronym appearances · ${bare.length} page(s) with a bare term`);
console.log('  exit 0 by design: a recorder. Read it via tools/read_recorder_findings.py.');
