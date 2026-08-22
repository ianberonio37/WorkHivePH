// prove_domain_truth.mjs — CI domain-truth, the family that has 176 rows owed and ZERO green.
//
// WHAT MAKES THIS FAMILY DIFFERENT. Every other family asks a question about software: did the read
// fail loudly, is the tap target 44px, did the dialog return focus. CI asks a question about
// ENGINEERING: is this the ISO 14224 definition of MTBF, does this OEE state which of A/P/Q is
// missing, does this reorder point name the threshold it crossed. A page can be flawless software and
// still be wrong here, and the person it misleads is a maintenance planner making a decision about a
// plant. That is why these 8-per-page oracles were hand-authored in the roadmap instead of templated.
//
// ★ THE ORACLE RISK IS THE WHOLE PROBLEM, AND IT HAS BITTEN FIVE TIMES THIS ARC. A domain-truth check
// is a keyword check wearing a lab coat, and a keyword check written at the desk measures its author:
//   · `no access` never matched the platform's own "do not have access" (CM why_refused)
//   · `[class*=loading]` never matched `<div id="dash-loading">Loading assets...</div>` (pm-scheduler)
//   · `level|lvl` never matched skillmatrix's `Lv 2 / 3`
//   · six spinner synonyms never matched assistant's three bouncing `.typing-dot`s
//   · four wait verbs never matched report-sender's own "Checking your saved contacts…"
// Every time the PRODUCT was right and the INSTRUMENT was narrow. So every pattern below was
// harvested from a live render (see .tmp/harvest.json), every check records the exact string it
// matched in `saw`, and `--selftest` plants both a satisfying and a violating text so a check that
// cannot fire is caught before it can bank a green.
//
// A NEGATIVE VERDICT HERE IS A CLAIM ABOUT ENGINEERING PRACTICE, so it is deliberately conservative:
// where the roadmap's truth needs a judgement no string can settle (does this cohort have enough n to
// be a benchmark?), the cell is reported UNGRADED rather than guessed. Vacuity is recorded, never
// counted — the same rule R10 applies to declared-na.
import { chromium } from 'playwright';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { pageUrl } from './page_query.mjs';
// The dialog/section open paths, READ FROM SOURCE. Reused here so this prover cannot drift from the
// five that already drive them — a second hand-rolled selector is how two walks end up measuring two
// different screens while both report success.
import { TARGETS } from './dialog_targets.mjs';
import fs from 'node:fs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const SELFTEST = args.includes('--selftest');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();
const OUT = ONE ? 'domain_truth.partial.json' : 'domain_truth_report.json';

// A check returns { ok, saw } — `saw` is the evidence, quoted from the page, so a verdict can be
// audited without re-running it. `null` for ok means UNGRADED (no subject on screen to judge).
const has = (t, re) => { const m = re.exec(t); return m ? m[0].replace(/\s+/g, ' ').trim() : null; };

// ★ A QUALIFIER MUST SIT NEAR THE FIGURE IT QUALIFIES, or the check reads the right words off the
// wrong part of the page. Measured 2026-08-15: the trend-period check accepted "calendar days between
// failures" — MTBF's basis, from a different card — as proof that the TREND was calendar-based. The
// words were present, the claim was not, and the cell went green. Same shape as a body-wide keyword
// match scoring a page on its own marketing copy.
// So: find the ANCHOR (the thing being claimed about), then look for the qualifier only within a
// window around it. Returns the matched qualifier, or null if it is not in that neighbourhood.
// ★ AND IT MUST TRY EVERY ANCHOR, NOT JUST THE FIRST. Measured minutes after the first version:
// skillmatrix renders "TOTAL BADGES 19 · 19 of 25 possible (5 levels × 5 disciplines)" — the
// denominator AND its formula, exactly what the row asks for — and the check FAILED it, because the
// first match of /badges/ on the page is the source chip's "Based on your skills & skill badges",
// 900 characters earlier. Anchoring on the first occurrence measured the wrong region and produced a
// false RED on a page doing the right thing, which is the same defect as the false GREEN it was
// written to fix, pointing the other way.
// So: scan ALL anchor occurrences, return the first window that actually contains the target.
const near = (t, anchorRe, targetRe, span = 140) => {
  const re = new RegExp(anchorRe.source, anchorRe.flags.includes('g') ? anchorRe.flags : anchorRe.flags + 'g');
  for (let a = re.exec(t); a; a = re.exec(t)) {
    const from = Math.max(0, a.index - span);
    const window = t.slice(from, a.index + a[0].length + span);
    const m = targetRe.exec(window);
    if (m) return m[0].replace(/\s+/g, ' ').trim();
    if (re.lastIndex === a.index) re.lastIndex++;   // zero-width guard
  }
  return null;
};

// ── THE TRUTHS ────────────────────────────────────────────────────────────────────────────────────
// Keyed by page, in the roadmap's own CI order, so `CI3` here is `CI3` there. `claim` is the roadmap's
// wording, shortened; `why` explains what a violation would cost the person reading the screen.
const TRUTHS = {
  // index is the ops home: every tile summarises a page that owns the same fact. Harvested live it
  // shows "Monday, Aug 17 · Morning Shift" and the tiles "9 OPEN JOBS / 29 PM OVERDUE / 3 LOW STOCK".
  index: [
    { id: 'CI1', claim: "a cron-fed daily figure says WHICH DAY it is for",
      check: (t) => {
        // The roadmap's wording: "a cron-fed number with no date is a stale number waiting to happen."
        const day = has(t, /\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+\w{3,9}\s+\d{1,2}[^\n]{0,24}/i);
        return { ok: !!day, saw: day || 'no date stated beside the day figures' };
      } },
  ],
  // alert-hub, harvested live: "HIGH-SEVERITY ALERTS 51 · 51 of 62 alerts need eyes now",
  // "ANOMALY SIGNALS 0 · No fused anomalies in your hive right now · CLEAR", and "AMC DAILY BRIEF
  // None today · No AMC brief for today's shift · NO BRIEF".
  'alert-hub': [
    { id: 'CI5', claim: '"0 alerts" distinguishes NOTHING WRONG from NOTHING COMPUTED YET',
      check: (t) => {
        // The most consequential zero on the platform. "0" alone is ambiguous in the one direction
        // that matters: a plant with nothing wrong and a plant nobody has looked at render alike.
        // ANCHORED TO THE SUMMARY CARDS, not the bare word ALERTS (2026-08-23): the generic anchor
        // swept the feed's FILTER-CHIP row ("Staging 0 · System 0" beside the "Alerts" heading) -
        // per-kind counts over a LOADED list of 62, where 0 unambiguously means "none of this kind
        // in the list below" and the nothing-computed ambiguity cannot arise. The domain zeros this
        // claim governs live on the summary cards, whose labels are the anchor.
        const zero = near(t, /ANOMALY SIGNALS|CRITICAL ALERTS/i, /\b0\b/, 60);
        if (!zero) return { ok: null, saw: 'no zero-valued alert figure on screen to judge' };
        const qualified = near(t, /\b0\b/, /no [a-z ]{0,24}(anomalies|alerts)[^\n]{0,30}|CLEAR|not (yet )?computed|nothing computed/i, 90);
        return { ok: !!qualified, saw: qualified || 'a bare 0 with nothing saying which kind of zero it is' };
      } },
    // ★ THIS CHECK ORIGINALLY TESTED A DENOMINATOR — which NO alert-hub row asks for. Row 109's oracle
    // is "alert AGE is shown - a 40-day-old alert must not read like a fresh one", and I nearly banked
    // "51 of 62 alerts" against it. A check with no matching row is not a bonus; it is a green waiting
    // to be attached to the wrong claim. Re-pointed at what row 109 actually asks.
    { id: 'CI7', claim: 'alert AGE is shown, so an old alert does not read like a fresh one (row 109)',
      check: (t) => {
        if (!/HIGH|MEDIUM|LOW|alerts?/i.test(t)) return { ok: null, saw: 'no alert rows on screen' };
        const age = has(t, /\b\d+\s*(min|minute|hour|hr|d|day|week)s?\s+ago\b/i);
        const n = (t.match(/\b\d+\s*(min|minute|hour|hr|d|day|week)s?\s+ago\b/gi) || []).length;
        return { ok: !!age, saw: age ? `${age} (${n} alert rows carry an age)`
          : 'alert rows shown with no age beside them' };
      } },
  ],
  // hive is walked so its text is available to the cross-surface pass (row 108 compares its low-stock
  // tile with inventory's own count). Its own single-surface truths stay owed rather than being
  // invented to fill the slot.
  hive: [
    // ★ RE-POINTED, FOR THE SECOND TIME IN THIS FILE. I first wrote this as "a composite score states
    // its BANDS", which hive does beautifully — "52 /100 composite risk · lower is better" with
    // "Tiers: healthy under 35 · at risk 35–65 · critical over 65". True, and NO hive row asks for it.
    // Row 103 asks something else: whether the READINESS composite states its INPUTS AND WEIGHTS
    // ("a 67/100 nobody can decompose is a vibe with a number attached"). Banking the bands evidence
    // against it would have asserted decomposability on the strength of a different score's tiers.
    // Same mistake as the alert-hub denominator-vs-age check earlier today; the tell both times was a
    // check I was pleased with that no row had asked for.
    // ★ READ THE BARS, NOT THE PAGE TEXT. `document.body.innerText` omits the dimension labels
    // entirely — #stair-dims returns '' from innerText while `textContent` gives "Process 100 Data 32
    // Resilience 70 Leadership 50 Culture 40". That is this project's recorded innerText trap, and it
    // made my check report "no dimension scores on the surface" about five scored bars a reader can
    // plainly see. Twice now this cell has been failed by the instrument rather than the page.
    { id: 'CI1', claim: 'the READINESS composite states its inputs and weights, so it can be decomposed',
      evalFn: () => {
        const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
          return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
        // ★ textContent INCLUDES <style> AND <script> TEXT, and that produced a FALSE GREEN: the
        // weights pattern matched `font-weight:700; letter-spacing:0` out of an inline stylesheet and
        // reported the composite as weighted. innerText would have excluded it — but innerText also
        // drops the dimension bars, which is why this check reads textContent in the first place. So
        // take textContent and remove the code, rather than choosing between two wrong accessors.
        const body = document.body;
        const strip = (root) => {
          const clone = root.cloneNode(true);
          clone.querySelectorAll('style, script, noscript, template').forEach((n) => n.remove());
          return clone.textContent || '';
        };
        const t = strip(body).replace(/\s+/g, ' ');
        const score = /HIVE READINESS[\s\S]{0,120}?(\d{1,3}\s*\/\s*100)/i.exec(t)
          || /(\d{1,3})\s*\/\s*100/.exec(t);
        if (!score) return { ok: null, saw: 'no readiness score on the board' };
        const bars = [...document.querySelectorAll('#stair-dims .stair-dim-bar')].filter(vis)
          .map((b) => (b.textContent || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
        const weights = /weight[^.]{0,40}|% of (the )?score[^.]{0,30}|combined? (as|by)[^.]{0,30}/i.exec(t);
        if (bars.length < 3) {
          return { ok: false, saw: `${score[0]} — fewer than three dimension scores are rendered, so the `
            + 'composite cannot be decomposed' };
        }
        return { ok: !!weights,
          saw: `${score[0]} | inputs: ${bars.join(' · ')}`
            + (weights ? ` | weights: ${weights[0]}`
              : ' | NO weighting stated — the five scores are shown but not how they combine into the composite') };
      } },
  ],
  // resume is the one page that makes an explicit, checkable promise about someone's PERSONAL
  // documents. The live half is that the promise is actually on screen where the upload happens; the
  // "then discarded" half is a fact about the whole chain (page → edge fn → table) and is recorded in
  // the row's evidence, because no amount of reading the rendered text can prove a file was not kept.
  resume: [
    { id: 'CI1', claim: 'the page makes its file-handling promise where the upload happens',
      check: (t) => {
        if (!/upload|resume/i.test(t)) return { ok: null, saw: 'no upload affordance on screen' };
        const promise = has(t, /read (just )?to fill[^\n]{0,60}|discard(ed)?[^\n]{0,60}|not (stored|kept)[^\n]{0,40}/i);
        return { ok: !!promise, saw: promise
          || 'files are invited with no statement of what happens to them afterwards' };
      } },
  ],
  // shift-brain plans a crew's next eight hours from an AI orchestrator's output. Harvested live:
  // "06-14 Morning / 14-22 Afternoon / 22-06 Night", "9 carry-forward", and "LOTO · PTW-2026-3875".
  'shift-brain': [
    // Row 110, and the one that matters most on this page: a permit-bearing task discovered AT THE
    // MACHINE is a person standing in front of energised equipment deciding whether to wait. In the
    // plan, it is a line they read before they walk over.
    { id: 'CI8', claim: 'LOTO / permit-bearing tasks are flagged IN THE PLAN, not discovered at the machine',
      check: (t) => {
        if (!/shift|plan/i.test(t)) return { ok: null, saw: 'no shift plan on screen' };
        const flag = has(t, /\bLOTO\b[^\n]{0,30}|\bpermit\b[^\n]{0,30}|\bPTW-[\w-]+/i);
        return { ok: !!flag, saw: flag || 'no LOTO or permit marker anywhere in the plan' };
      } },
    { id: 'CI3', claim: 'carry-over is DEFINED: not-done, deferred and blocked are three different states',
      check: (t) => {
        const carry = has(t, /carry-?(forward|over)[^\n]{0,40}/i);
        if (!carry) return { ok: null, saw: 'no carry-over figure on screen' };
        // The row's point: one bucket labelled "carried" hides three situations with three different
        // recoveries — nobody started it, someone chose to postpone it, something is preventing it.
        const states = ['defer', 'block', 'not started', 'not done', 'waiting']
          .filter((w) => new RegExp(w, 'i').test(t));
        return { ok: states.length >= 2,
          saw: states.length >= 2 ? `${carry} | states named: ${states.join(', ')}`
            : `${carry} — one bucket, and no distinction between not-started, deferred and blocked` };
      } },
  ],
  // dayplanner's four period views are named by acronym. The roadmap's gloss: "an acronym nobody can
  // expand is jargon at the exact moment it costs someone their day."
  dayplanner: [
    { id: 'CI1', claim: 'DILO / WILO / MILO / YILO are EXPANDED on the surface, not left as acronyms',
      // Only the active tab renders, so grading the default view would settle one quarter of the row
      // and leave three unexamined. This drives each tab and reads the expansion beside its acronym.
      // (First attempt used a line-bounded regex on the default view and reported DILO as bare — the
      // expansion "Day In the Life Of" sits on the NEXT line. The page was right; the pattern stopped
      // at the newline.)
      evalFn: async () => {
        const WANT = { dilo: /day in the life/i, wilo: /week in the life/i,
                       milo: /month in the life/i, yilo: /year in the life/i };
        const seen = {}, missing = [];
        for (const key of Object.keys(WANT)) {
          const tab = document.getElementById('tab-' + key) || document.querySelector(`[data-tab="${key}"]`);
          if (!tab) { missing.push(`${key.toUpperCase()} (no tab found)`); continue; }
          tab.click();
          await new Promise((r) => setTimeout(r, 700));
          const txt = (document.body.innerText || '').replace(/\s+/g, ' ');
          const m = WANT[key].exec(txt);
          if (m) seen[key.toUpperCase()] = m[0]; else missing.push(key.toUpperCase());
        }
        return { ok: missing.length === 0,
          saw: missing.length === 0
            ? ('all four expanded: ' + Object.entries(seen).map(([k, v]) => `${k}=${v}`).join(', '))
            : (`expanded: ${Object.keys(seen).join(', ') || 'none'} — NOT expanded: ${missing.join(', ')}`) };
      } },
  ],
  analytics: [
    { id: 'CI1', claim: 'OEE follows ISO 22400 and the surface says which factor drags it down',
      check: (t) => {
        const std = has(t, /ISO\s*22400[-\d:]*/i);
        // The page's own honest phrasing, harvested live: it names the factors it HAS and the one it
        // lacks ("Availability × Quality only. Add each asset's cycle time to include Performance").
        const factors = has(t, /Availability\s*[×x]\s*\w+[^.]*/i);
        return { ok: !!(std && factors), saw: [std, factors].filter(Boolean).join(' | ') };
      } },
    { id: 'CI2', claim: 'a partial OEE is LABELLED partial rather than presented as OEE',
      check: (t) => {
        const oee = /OEE/i.test(t);
        if (!oee) return { ok: null, saw: 'no OEE figure on screen' };
        const partial = has(t, /OEE[^\n]{0,40}\bPARTIAL\b|\bPARTIAL\b[^\n]{0,40}OEE/i);
        return { ok: !!partial, saw: partial || 'OEE shown with no partial qualifier' };
      } },
    // Row 105's oracle is "MTBF/MTTR follow ISO 14224 AND MATCH logbook and hive to the same decimal".
    // The cross-surface half needs three pages read together, which this walk does not do, so this
    // check settles only the half it can and reports the row as UNGRADED rather than green. Banking
    // the standard-is-named half against a row that also demands agreement is exactly the
    // over-claim this file exists to avoid; the row stays owed until the comparison is built.
    { id: 'CI3', claim: 'MTBF/MTTR follow ISO 14224 AND match logbook and hive to the same decimal',
      check: (t) => {
        const std = has(t, /ISO\s*14224[-\d:]*/i);
        const basis = has(t, /(calendar days|running hours|operating (time|hours))[^.\n]*/i);
        if (!std) return { ok: false, saw: 'MTBF shown without naming ISO 14224' };
        return { ok: null, saw: `${[std, basis].filter(Boolean).join(' | ')} — standard and basis are `
          + 'stated; the cross-surface half (matches logbook and hive to the same decimal) is not '
          + 'checked by this walk, so the row stays owed rather than banking on half its oracle' };
      } },
    { id: 'CI4', claim: 'PM on-time delivery states its tolerance window',
      check: (t) => {
        if (!/PM COMPLIANCE|on-?time/i.test(t)) return { ok: null, saw: 'no PM compliance figure on screen' };
        // Scoped to the compliance card. Unscoped, this matched a stray "6d" from elsewhere on the
        // page and called it the tolerance window — a number that had nothing to do with the claim.
        // `within each PM's own interval` accepted here for the same reason as pm-scheduler's row: it
        // is what this platform's tolerance IS, read from get_pm_ontime_delivery
        // (`completed_at <= prev_at + frequency_days`). Demanding "± N days" would demand a number the
        // model does not have and would push the surface to invent one. Both cards now carry the same
        // sentence, so a reader moving between them is not handed two meanings of one word.
        const win = near(t, /PM COMPLIANCE|on-?time/i, /within\s+\d+\s*days?|±\s*\d+\s*days?|\b\d+\s*day\s*(window|tolerance|grace)|within each PM[^\n]{0,24}interval/i, 200);
        const std = near(t, /PM COMPLIANCE/i, /SMRP[^\n]{0,12}/i, 120);
        return { ok: !!win, saw: [std, win].filter(Boolean).join(' | ')
          || `${std || 'compliance'} — shown with no tolerance window stated` };
      } },
    // ★ THE CHECK MUST BE THE ROW'S ORACLE, NOT A WEAKER COUSIN OF IT. Row 108 asks for the period
    // AND whether it is rolling or calendar; row 110 asks for the RULE behind the verdict, not merely
    // a basis affordance. My first drafts checked only the easy half of each, which would have banked
    // a green against a claim it never tested — the "oracle that does not match the claim" defect,
    // and the most expensive kind because the row then asserts the property forever.
    { id: 'CI6', claim: 'a trend states its period AND whether it is rolling or calendar',
      check: (t) => {
        const per = has(t, /\b(30|90|180)\s*days?\b|\b1\s*year\b/i);
        if (!per) return { ok: false, saw: 'no period stated' };
        // Scoped to the period selector itself — "calendar days between failures" sits on the MTBF
        // card and says nothing about how the TREND window is anchored.
        // `last N days` was in this vocabulary and matched a DIFFERENT figure's window, turning the
        // check green on borrowed words. It is also ambiguous on its own — a selector label, not a
        // statement about how the trend is anchored. Only the explicit words count.
        // `calendar day` had to go too: "calendar days between failures" is MTBF's BASIS, and with
        // `day` in this alternation it kept satisfying a claim about the TREND window. A trend is
        // anchored to a calendar MONTH/WEEK/YEAR or it rolls; "calendar days" says neither.
        const kind = near(t, /\b(30|90|180)\s*days?\b/i, /\brolling\b|\bcalendar (month|year|week)s?\b/i, 90);
        return { ok: !!kind, saw: kind ? `${per} | ${kind}`
          : `${per} — period stated, but not whether it is rolling or calendar` };
      } },
    { id: 'CI8', claim: 'the verdict states the RULE that produced it, not only the conclusion',
      check: (t) => {
        if (!/WHAT TO DO NEXT|verdict|recommendation/i.test(t)) {
          return { ok: null, saw: 'no verdict/recommendation block on screen' };
        }
        // A basis affordance ("Based on your logbook") says where the DATA came from. The oracle asks
        // for the RULE — the threshold or comparison that produced this conclusion rather than another.
        const rule = has(t, /because [^\n]{0,60}|threshold[^\n]{0,40}|below [^\n]{0,40}|at or below[^\n]{0,40}/i);
        const basis = has(t, /How this is computed|Based on your [^\n]{0,40}/i);
        return { ok: !!rule, saw: rule ? `${rule}` : `${basis || 'verdict'} — basis named, but not the rule that fired` };
      } },
  ],
  // asset-hub carries the roster's highest-stakes reliability claims. Harvested from the asset-detail
  // view of BE-001, which renders: "Weibull beta=2.62, eta=243d -> wear-out region; hazard rises with
  // age." and "Top approved FMEA RPN 180 (Coupling misalignment beyond 0.05 m...)".
  // NOTE ON SCOPE: the S/O/D scales (CI1) and the P-F interval (CI4) live behind the FMEA and P-F
  // modals, which this walk does not open. They are therefore NOT graded here — grading a view I did
  // not reach is exactly the paramless-walk defect that produced a false red earlier in this arc.
  // They stay owed until a walk opens those modals, which is honest; a red would not be.
  'asset-hub': [
    // Row 103 wants BOTH halves: the S/O/D scales stated, AND the threshold that makes an RPN critical
    // ("an RPN of 120 means nothing without its bands"). The FMEA panel does something genuinely good
    // here — a worked example naming each factor in plain English ("Severity 7 (hurts output) ×
    // Occurrence 4 (a few times a year) × Detection 5 (only caught on inspection) = RPN 140") — so the
    // check must not credit that as the whole claim. Explaining what a factor MEANS is not stating its
    // RANGE, and "fix the 140 first" is a relative rule, not a band.
    { id: 'CI1', claim: 'the S/O/D scales are stated AND the RPN critical threshold is named',
      check: (t) => {
        if (!/\bRPN\b/i.test(t)) return { ok: null, saw: 'no RPN figure on the reached view' };
        const scale = has(t, /\b1\s*[-–]\s*10\b|scale of 1[^\n]{0,12}10|out of 10/i);
        const band = has(t, /critical (above|over|at|when)[^\n]{0,24}|RPN\s*[>≥]\s*\d{2,3}|\bbands?\b[^\n]{0,24}/i);
        return { ok: !!(scale && band),
          saw: (scale || band)
            ? `${scale ? 'scale: ' + scale : 'NO 1-10 scale stated'} | ${band ? 'band: ' + band : 'NO critical threshold named'}`
            : 'the factors are explained in words, but neither the 1-10 range nor a critical band is '
              + 'stated, so an RPN of 180 cannot be placed - severe, or middling out of a 1000 maximum?' };
      } },
    { id: 'CI2', claim: 'beta is INTERPRETED on the surface (<1 infant, ~1 random, >1 wear-out)',
      check: (t) => {
        const b = has(t, /beta\s*=\s*[\d.]+/i);
        if (!b) return { ok: null, saw: 'no Weibull beta on this view' };
        // A bare beta is a number nobody can act on; the page must say what the shape MEANS.
        const meaning = has(t, /(wear-?out|infant mortality|random failure)[^.\n]{0,60}/i);
        return { ok: !!meaning, saw: [b, meaning].filter(Boolean).join(' -> ')
          || `${b} shown with no interpretation` };
      } },
    { id: 'CI3', claim: 'eta carries its unit (hours vs days vs cycles)',
      check: (t) => {
        const e = has(t, /eta\s*=\s*[\d.]+\s*[a-z]+/i);
        if (!/eta\s*=/i.test(t)) return { ok: null, saw: 'no Weibull eta on this view' };
        // "eta=243d" — the unit is the trailing token. A unitless eta is unusable.
        return { ok: !!e && /[a-z]/i.test(e.replace(/eta\s*=\s*[\d.]+/i, '')), saw: e || 'eta with no unit' };
      } },
    // ★ ROW 108 IS NOT WHAT I FIRST WROTE HERE. Its oracle is "sensor readings state their AGE, and
    // v_sensor_recent vs v_sensor_truth are visibly different questions" — about SENSOR data, and
    // about two views being distinguishable. My original check tested the page's snapshot-computed-at
    // stamp, which is a real property and a DIFFERENT one. Banking it against row 108 would have
    // asserted something about sensor freshness on the strength of a dashboard timestamp.
    // Kept, correctly scoped to sensor readings, and it now reports UNGRADED when no sensor panel is
    // on the walked view rather than crediting the snapshot stamp in its place.
    { id: 'CI6', claim: 'sensor readings state their AGE (row 108), not merely the dashboard snapshot time',
      check: (t) => {
        if (!/sensor|reading/i.test(t)) return { ok: null, saw: 'no sensor panel on the walked view' };
        // ★ THE VOCABULARY IS whFmtAgo's OWN OUTPUT, not my idea of how an age is written. That helper
        // (utils.js:2005) emits exactly four forms — "just now", "Nm ago", "Nh ago", "Nd ago" — and my
        // pattern demanded the words spelled out (`day`, `hour`), so it missed the platform's real
        // "27d ago". Seventh narrow-oracle correction this arc, and the fix is the same every time:
        // read the vocabulary off the thing that produces it.
        const age = near(t, /sensor|reading|latest/i,
          /\b\d+\s*[dhm]\s*ago\b|\b\d+\s*(min|minute|hour|hr|day)s?\s*ago\b|\bjust now\b|as of [^\n]{0,20}/i, 140);
        return { ok: !!age, saw: age || 'sensor readings shown with no age beside them' };
      } },
  ],
  // pm-scheduler, harvested live: "80% PM compliance (SMRP)" and "72.1% done on time · 114 of 409 ran
  // late" — the denominator is on the surface, which is exactly what CI1 asks for.
  'pm-scheduler': [
    { id: 'CI1', claim: 'SMRP PM compliance names its DENOMINATOR (completed-on-time / scheduled)',
      check: (t) => {
        if (!/compliance|on time/i.test(t)) return { ok: null, saw: 'no compliance figure on screen' };
        // "a label that omits the half is a claim" — the roadmap's own wording. Scoped, so a stray
        // "N of M" from the asset tiles cannot stand in for the compliance denominator.
        // ★ ANCHOR ON THE SPECIFIC PHRASE, NOT THE FAMILY. Anchored on /PM compliance/ this matched
        // "0 of 30" — the assets-on-track count sitting one tile away — and called it the compliance
        // denominator. On a page dense with "N of M" figures, proximity alone is not enough: the
        // anchor has to be the exact claim ("done on time" / "ran late"), whose denominator is the
        // "114 of 409" the page actually prints beside it.
        // Even anchored, a window returns whichever "N of M" comes FIRST — here "0 of 30 on track",
        // one clause earlier, which is an ASSET count, not the compliance denominator. When the page
        // prints the denominator inside a fixed phrase, match the PHRASE: "114 of 409 ran late"
        // cannot be mistaken for anything else on the screen.
        const den = has(t, /\d[\d,]*\s+of\s+\d[\d,]*\s+ran late/i);
        const std = has(t, /SMRP[^\n)]{0,10}/i);
        return { ok: !!den, saw: [std, den].filter(Boolean).join(' | ')
          || 'compliance % shown with no denominator beside it' };
      } },
    // Row 107: "the compliance window (90 days, per the RPC call the page actually makes) is named
    // wherever the % appears". The window is not a guess — pm-scheduler.html:1399 calls
    // `get_pm_compliance_smrp` with `p_period_days: 90`, so the page knows the number and simply does
    // not print it. The check looks for ANY explicit window beside the %, not for "90" specifically:
    // naming a different-but-stated window would be a different finding, and demanding the exact digits
    // would fail a page that said "over the last quarter".
    { id: 'CI5', claim: 'the compliance window (90d, per the RPC this page calls) is named where the % appears',
      check: (t) => {
        if (!/compliance/i.test(t)) return { ok: null, saw: 'no compliance figure on screen' };
        const win = near(t, /compliance/i, /\b\d+\s*days?\b|\bquarter\b|\blast\s+\d+\s*days?\b|\b90d\b/i, 150);
        return { ok: !!win, saw: win
          || 'compliance % shown with no window named; the only window on screen is the DUE SOON (14D) '
           + 'lookahead, which is a different figure a reader could easily take for this one' };
      } },
    { id: 'CI2', claim: 'on-time is defined against a stated TOLERANCE window, and the window is on screen',
      check: (t) => {
        if (!/on time|overdue/i.test(t)) return { ok: null, saw: 'no on-time figure on screen' };
        // ★ "DUE SOON (14D)" IS NOT A TOLERANCE. It is a LOOKAHEAD — which PMs fall due in the next
        // fortnight — and it says nothing about how late a completion may be and still count as "on
        // time". Accepting it here passed the cell on a window that answers a different question, and
        // I only caught it by reading the row's oracle word for word against the evidence. A tolerance
        // is a grace period around a due date; a lookahead is a planning horizon.
        // `within each PM's own interval` added to the accepted forms because that is what this
        // platform's tolerance actually IS — read from get_pm_ontime_delivery: a completion is on time
        // when `completed_at <= prev_at + frequency_days`. There is no fixed grace period, so
        // demanding "± N days" would demand a number the model does not have, and would push the page
        // to invent one. Harvested from the implementation, not from my idea of what a tolerance
        // looks like.
        const win = has(t, /within\s+\d+\s*days?\s*(of|after)|±\s*\d+\s*days?|\b\d+\s*day\s*(tolerance|grace)|grace period[^\n]{0,20}|within each PM[^\n]{0,24}interval/i);
        return { ok: !!win, saw: win
          || 'on-time % reported with no tolerance window; the only window on screen is the DUE SOON '
           + 'lookahead, which answers a different question' };
      } },
  ],
  // (continues 'pm-scheduler' above — kept adjacent to CI1/CI2 for the same page)
  // skillmatrix, harvested live: "19 of 25 possible (5 levels × 5 disciplines)" — the denominator AND
  // the formula behind it. This is the page where a malformed credential claim costs someone work.
  skillmatrix: [
    { id: 'CI7', claim: 'matrix coverage states its denominator — which skills, which workers',
      check: (t) => {
        const den = near(t, /badges?|coverage|on target/i, /\d+\s+of\s+\d+\s*(possible)?[^\n]{0,40}/i, 140);
        return { ok: !!den, saw: den || 'coverage shown with no denominator' };
      } },
  ],
  inventory: [
    { id: 'CI1', claim: 'reorder point is the low-stock trigger, and the badge names the point crossed',
      check: (t) => {
        // Harvested: "3 of 27 parts at or below min_qty" and "at or below the reorder threshold".
        const named = has(t, /at or below (the )?(min_qty|reorder threshold|minimum)[^\n]{0,20}/i);
        return { ok: !!named, saw: named || 'low-stock shown without naming its threshold' };
      } },
    { id: 'CI2', claim: 'lead time is stated wherever a reorder is suggested',
      check: (t) => {
        // ★ THE SUBJECT GATE WAS NARROWER THAN THE PAGE, which would have marked a real reorder
        // suggestion "no subject" and quietly ungraded it — the failure mode that shrinks a
        // denominator instead of reporting a gap. Harvested live, inventory says "Order 3 low parts →"
        // and "Order them before the next shift planning", so the gate accepts "order <n>" too.
        // Caught by --selftest: the violating case scored `null` instead of `false`.
        if (!/reorder|restock|order (them|\d+)/i.test(t)) return { ok: null, saw: 'no reorder suggestion on screen' };
        const lead = has(t, /lead[- ]?time[^\n]{0,30}|arrives? in \d+[^\n]{0,20}|\b\d+\s*(day|week)s?\s*(to|for)\s*deliver/i);
        return { ok: !!lead, saw: lead || 'reorder suggested with no lead time' };
      } },
    // ★ "EVERY" IS THE WORD THAT MAKES THIS A DOM CHECK, NOT A TEXT MATCH. Row 105 asks that the unit
    // travels with EVERY quantity; finding one "2 pcs" in the page text proves only that ONE does, and
    // banking that would assert the other 26 parts on no evidence at all. So this walks the rendered
    // part cards and pairs each quantity element with the token beside it — the markup read at
    // inventory.html:1133-1134, where the qty span is immediately followed by the unit span.
    { id: 'CI3', claim: 'the unit of measure travels with EVERY quantity, not merely one',
      evalFn: () => {
        const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
          return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
        // ★ THE UNIT VOCABULARY IS HARVESTED FROM THE DATA, NOT INVENTED. The first list omitted
        // `tubes`, so a part correctly rendered as "3 tubes" was reported as a quantity with NO unit —
        // a false finding against a page doing exactly what the row asks, and the sixth time this arc
        // an oracle was narrower than the product. The authority is the column itself:
        //   select distinct unit from inventory_items;  ->  kg, L, pcs, rolls, tubes
        // Kept broader than today's data (a new unit must not create a false red tomorrow) but every
        // value the platform actually stores is present.
        const UNIT = /^(pcs|pieces|tubes?|rolls?|kg|g|l|litres?|liters?|m|metres?|meters?|sets?|boxes|units?|ea)$/i;
        const qtys = [...document.querySelectorAll('span.text-3xl')].filter(vis);
        if (!qtys.length) return { ok: null, saw: 'no rendered quantity elements on this view' };
        const bare = [];
        for (const q of qtys) {
          const sib = q.nextElementSibling;
          const txt = ((sib && (sib.innerText || sib.textContent)) || '').trim();
          if (!UNIT.test(txt)) bare.push((((q.innerText || q.textContent) || '?').trim()) + ' -> "' + txt + '"');
        }
        return { ok: bare.length === 0,
          saw: bare.length === 0
            ? ('all ' + qtys.length + ' rendered quantities carry a unit beside them')
            : (bare.length + ' of ' + qtys.length + ' quantities have no unit: ' + bare.slice(0, 3).join(', ')) };
      } },
    // ★ THIS IS THE ONE SCREEN WHERE THE DISTINCTION IS ACTED ON, so the check drives it rather than
    // pattern-matching the list. On-hand and available differ only when a part is staged against a
    // predicted failure, so the walk finds a card the page itself marks "N reserved", opens ITS Use
    // modal through the page's own opener, and reads the line a person commits a quantity against.
    // Measured 2026-08-17 before the fix: BRG-6310 with on_hand 2 and qty_reserved 1 said
    // "Available: 2 pcs" — on-hand printed under the permissive label, inviting a technician to take
    // the part staged for the failure the reservation exists to cover.
    { id: 'CI7', claim: 'on-hand and AVAILABLE (minus staged reservations) are two numbers, both labelled',
      evalFn: async () => {
        const chip = [...document.querySelectorAll('*')].find((el) => !el.children.length
          && /\d+\s+reserved/i.test(el.textContent || ''));
        if (!chip) return { ok: null, saw: 'no part on this view carries a staged reservation, so the two '
          + 'numbers cannot differ here and the distinction is not observable' };
        // ★ `closest('div')` REACHES THE IMMEDIATE PARENT, NOT THE CARD. The first version used it and
        // found nothing, so this cell reported UNGRADED — honest, but blind. The Use button and the
        // "N reserved" chip live in different branches of the same card, so the walk has to climb until
        // one ancestor contains BOTH.
        const btn = [...document.querySelectorAll('[onclick^="openUseModal"]')].find((b) => {
          for (let n = b.parentElement, i = 0; n && i < 8; n = n.parentElement, i++) {
            if (n.contains(chip)) return true;
          }
          return false;
        });
        const m = btn && (btn.getAttribute('onclick') || '').match(/openUseModal\('([^']+)'\)/);
        if (!m || typeof window.openUseModal !== 'function') {
          return { ok: null, saw: 'could not reach the Use modal for the reserved part' };
        }
        window.openUseModal(m[1]);
        await new Promise((r) => setTimeout(r, 900));
        const line = ((document.getElementById('use-qty-available') || {}).textContent || '').trim();
        // Both numbers, both labelled: an "Available: N" that silently equals on-hand is the defect.
        const ok = /available:\s*\d/i.test(line) && /on hand/i.test(line) && /staged|reserved/i.test(line);
        return { ok, saw: line || 'the Use modal showed no availability line at all' };
      } },
  ],
};

// ★ SOME TRUTHS LIVE ONE CLICK IN, AND A WALK THAT DOES NOT REACH THEM MUST NOT GRADE THEM.
// asset-hub's Weibull line renders on the ASSET DETAIL view, not the list. Walking the list and
// reporting "no beta on screen" would be true about the list and meaningless about the claim — the
// same shape as grading project-report's "No project specified" shell as the page. So each page may
// declare how to REACH the view its truths are about, and a reach that fails is reported rather than
// silently walked past.
const REACH = {
  'asset-hub': async (page) => {
    // ★ USE THE REGISTRY'S OWN PRECONDITION, NOT A HAND-ROLLED SELECTOR. My first version clicked
    // `[onclick*="openAsset"], .asset-card, [data-asset-id]` and REPORTED SUCCESS — it found something,
    // clicked it, and the FMEA tab click afterwards also succeeded — but the captured text never
    // contained the panel's legend, because that path reaches a different view from the one
    // dialog_targets was written against. A reach that "works" and lands somewhere else is the
    // paramless-walk defect in miniature: every downstream verdict is about a screen I did not intend.
    // The registry's `pre` (a STRING of page JS, evaluated) resolves the node the workbench needs.
    const t = TARGETS.find((x) => x.page === 'asset-hub' && x.view === 'V2');
    if (t && t.pre) { await page.evaluate(t.pre); await page.waitForTimeout(1600); }
    const clicked = await page.evaluate(() => {
      const c = document.querySelector('[data-node-id], [onclick*="openAsset"], .asset-card');
      if (!c) return null;
      c.click();
      return c.textContent.replace(/\s+/g, ' ').trim().slice(0, 40);
    });
    if (!clicked) return { ok: false, note: 'no asset row was clickable, so the 360 view was never opened' };
    await page.waitForTimeout(4500);
    // Row 103's subject (the S/O/D scales and the RPN bands) lives in the FMEA panel, one tab deeper.
    // The opener comes from the dialog_targets registry rather than a guess: an ad-hoc
    // [data-tab="fmea"] matched something else entirely and returned the summary text unchanged three
    // times, which looked like "the tabs do not switch" and was really "I clicked the wrong element".
    const fmea = await page.evaluate(() => {
      const el = document.querySelector('.rel-tab[data-tab="fmea"]');
      if (!el) return false; el.click(); return true;
    });
    await page.waitForTimeout(2500);
    return { ok: true, note: `opened ${clicked}${fmea ? ' + FMEA panel' : ' (FMEA tab absent)'}` };
  },
};

const SELFTEST_CASES = [
  { page: 'analytics', id: 'CI2',
    satisfies: 'OEE (AVG, PARTIAL) - Unavailable', violates: 'OEE 82% healthy' },
  // CI3 deliberately returns UNGRADED when the standard IS named, because the row also demands
  // cross-surface agreement this walk does not check. So its planted pair asserts null-vs-false, not
  // true-vs-false: the check must still FAIL when the standard is absent entirely.
  { page: 'analytics', id: 'CI3', expect: [null, false],
    satisfies: 'ISO 14224:2016 - Counts calendar days between failures, not running hours.',
    violates: 'WORST MTBF 41 days' },
  { page: 'inventory', id: 'CI1',
    satisfies: '3 of 27 parts at or below min_qty', violates: 'LOW STOCK 3' },
  { page: 'inventory', id: 'CI2',
    satisfies: 'Reorder now - lead time 14 days from supplier', violates: 'Order 3 low parts' },
  { page: 'pm-scheduler', id: 'CI1',
    satisfies: '80% PM compliance (SMRP) 72.1% done on time - 114 of 409 ran late',
    violates: '80% PM compliance (SMRP)' },
  { page: 'skillmatrix', id: 'CI7',
    satisfies: 'TOTAL BADGES 19 of 25 possible (5 levels x 5 disciplines)',
    violates: 'TOTAL BADGES 19' },
  { page: 'alert-hub', id: 'CI5',
    satisfies: 'ANOMALY SIGNALS 0 No fused anomalies in your hive right now CLEAR',
    violates: 'ANOMALY SIGNALS 0' },
  { page: 'alert-hub', id: 'CI7',
    satisfies: 'HIGH BE-001 2d ago Multiple failure types on BE-001',
    violates: 'HIGH BE-001 Multiple failure types on BE-001' },
  { page: 'asset-hub', id: 'CI2',
    satisfies: 'Weibull beta=2.62, eta=243d -> wear-out region; hazard rises with age.',
    violates: 'Weibull beta=2.62, eta=243d' },
  { page: 'asset-hub', id: 'CI3',
    satisfies: 'Weibull beta=2.62, eta=243d', violates: 'Weibull beta=2.62, eta=243' },
];

if (SELFTEST) {
  let bad = 0;
  for (const c of SELFTEST_CASES) {
    const t = TRUTHS[c.page].find((x) => x.id === c.id);
    const pos = t.check(c.satisfies), neg = t.check(c.violates);
    const [wantPos, wantNeg] = c.expect || [true, false];
    const ok = pos.ok === wantPos && neg.ok === wantNeg;
    if (!ok) bad++;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${c.page}/${c.id}: satisfying->${pos.ok} violating->${neg.ok}`);
    if (!ok) console.log(`     saw+: ${pos.saw}\n     saw-: ${neg.saw}`);
  }
  console.log(bad ? `\n${bad} check(s) cannot discriminate — they would bank verdicts they never tested.`
                  : '\nevery check fires on a satisfying text AND fails on a violating one');
  process.exit(bad ? 1 : 0);
}

// ── CROSS-SURFACE TRUTHS ──────────────────────────────────────────────────────────────────────────
// The roadmap states this one for nearly every page: a figure shown on two surfaces must AGREE. It is
// the classic defect — the summary is written once and the detail keeps moving — and it cannot be
// checked from a single page, so these run after the walk, over the collected texts.
// Both sides are extracted with the SAME regex family and each side's matched string is recorded, so a
// disagreement names both numbers rather than asserting one is wrong.
const CROSS = [
  // hive row 108. The same fact on a third surface, and the comparison is NON-VACUOUS for the same
  // reason index's was: against this hive the reorder-point predicate returns 3 while a hardcoded
  // `qty_on_hand < 10` returns 8, so agreeing on 3 can only have come from the per-part threshold.
  { id: 'CI8', page: 'hive', claim: "hive's low-stock count equals inventory's own reorder-point count",
    a: { page: 'hive', re: /(\d+)\s*\n?\s*Parts low on stock/i },
    b: { page: 'inventory', re: /(\d+)\s+low\b/i },
    why: 'the board and the page it summarises are the same fact, and a supervisor acts on whichever they open first' },
  { id: 'CI6', page: 'index', claim: "index's LOW STOCK tile equals inventory's own low count",
    a: { page: 'index', re: /(\d+)\s*\n?\s*LOW STOCK/i },
    b: { page: 'inventory', re: /(\d+)\s+low\b/i },
    why: 'the tile and the page it summarises are the same fact; a technician acts on whichever they see first' },
];

const browser = await chromium.launch();
const cells = [];
const TEXTS = {};
for (const page_ of (ONE ? [ONE.replace(/\.html$/, '')] : Object.keys(TRUTHS))) {
  const truths = TRUTHS[page_];
  if (!truths) { console.log(`  ${page_}: no truths authored yet`); continue; }
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 1600 } });
  await assertSignedIn(signIn(ctx, 'supervisor'));
  const page = await ctx.newPage();
  await page.goto(pageUrl(ORIGIN, page_), { waitUntil: 'domcontentloaded', timeout: 25000 });
  await page.waitForTimeout(9000);
  if (REACH[page_]) {
    const reached = await REACH[page_](page)
      .catch((e) => ({ ok: false, note: String(e.message || e).slice(0, 80) }));
    console.log(`  ${page_}: reach — ${reached.note}`);
    if (!reached.ok) {
      for (const t of truths) {
        cells.push({ page: page_, id: t.id, ok: null, claim: t.claim,
          verdict: `UNGRADED: could not reach the view these truths are about (${reached.note}). `
                 + 'Grading the screen I landed on instead would be a verdict about a different view.' });
      }
      await page.close(); await ctx.close();
      continue;
    }
  }
  const text = await page.evaluate(() => (document.body.innerText || '').replace(/ /g, ' '));
  TEXTS[page_] = text;
  // The page stays OPEN until the truths have run: a structural claim ("every quantity carries a
  // unit") is settled by walking the DOM, not by matching a flat string, so those checks need a live
  // page. Closed at the end of the block instead.

  // ★ A PAGE THAT DID NOT RENDER CANNOT BE JUDGED ON ITS DOMAIN CLAIMS. Measured this session: with
  // the edge runtime down, analytics rendered 1211 chars of "Analytics unavailable" — correct
  // behaviour, and every domain truth would have "failed" for want of a figure to state a standard
  // about. That is the dead-fixture defect: the instrument grading its own broken environment.
  if (/name resolution failed|Analytics unavailable|engine warming up/i.test(text)) {
    for (const t of truths) {
      cells.push({ page: page_, id: t.id, ok: null, claim: t.claim,
        verdict: 'UNGRADED: the page rendered a dependency-failure state, so there were no domain '
               + 'figures on screen to judge. Not a defect — the page said so correctly.' });
    }
    console.log(`  ${page_}: UNGRADED (dependency-failure state on screen)`);
    await page.close(); await ctx.close();
    continue;
  }

  for (const t of truths) {
    const r = t.evalFn ? await page.evaluate(t.evalFn) : t.check(text);
    cells.push({ page: page_, id: t.id, ok: r.ok, claim: t.claim, saw: r.saw,
      verdict: r.ok === null ? `UNGRADED: ${r.saw}`
             : r.ok ? `states it: "${r.saw}"`
             : `the surface does not state this: ${r.saw}` });
  }
  await page.close(); await ctx.close();
  const g = cells.filter((c) => c.page === page_ && c.ok === true).length;
  const f = cells.filter((c) => c.page === page_ && c.ok === false).length;
  const u = cells.filter((c) => c.page === page_ && c.ok === null).length;
  console.log(`  ${page_.padEnd(18)} states ${g}  missing ${f}  ungraded ${u}`);
  for (const c of cells.filter((x) => x.page === page_ && x.ok === false)) {
    console.log(`     ✗ ${c.id}: ${c.claim}`);
    console.log(`        ${c.saw}`);
  }
}
await browser.close();

// ── the cross-surface pass ────────────────────────────────────────────────────────────────────────
// Runs only where BOTH surfaces were walked in this run; a comparison against a page we did not read
// is not a weaker check, it is no check, so it is reported UNGRADED rather than skipped silently.
for (const c of CROSS) {
  if (ONE && ONE.replace(/\.html$/, '') !== c.page) continue;
  const ta = TEXTS[c.a.page], tb = TEXTS[c.b.page];
  if (!ta || !tb) {
    cells.push({ page: c.page, id: c.id, ok: null, claim: c.claim,
      verdict: `UNGRADED: needs both ${c.a.page} and ${c.b.page} in the same run; `
             + `${!ta ? c.a.page : c.b.page} was not walked.` });
    continue;
  }
  const ma = c.a.re.exec(ta), mb = c.b.re.exec(tb);
  if (!ma || !mb) {
    cells.push({ page: c.page, id: c.id, ok: null, claim: c.claim,
      verdict: `UNGRADED: the figure was not on screen on ${!ma ? c.a.page : c.b.page}, so there is `
             + 'nothing to compare. A missing number is not a disagreeing number.' });
    continue;
  }
  const agree = ma[1] === mb[1];
  cells.push({ page: c.page, id: c.id, ok: agree, claim: c.claim,
    saw: `${c.a.page}="${ma[0].replace(/\s+/g, ' ').trim()}" vs ${c.b.page}="${mb[0].replace(/\s+/g, ' ').trim()}"`,
    verdict: agree
      ? `both surfaces say ${ma[1]}`
      : `DISAGREE: ${c.a.page} says ${ma[1]}, ${c.b.page} says ${mb[1]} — ${c.why}` });
  console.log(`  cross ${c.id}: ${agree ? 'agree' : 'DISAGREE'} (${c.a.page}=${ma[1]}, ${c.b.page}=${mb[1]})`);
}

const totals = { cells: cells.length, states: cells.filter((c) => c.ok === true).length,
                 missing: cells.filter((c) => c.ok === false).length,
                 ungraded: cells.filter((c) => c.ok === null).length };
fs.writeFileSync(OUT, JSON.stringify({ totals, cells }, null, 1));
console.log(`\n${totals.cells} cell(s): ${totals.states} stated · ${totals.missing} missing · `
  + `${totals.ungraded} ungraded  ->  ${OUT}`);
process.exit(GATE && totals.missing ? 1 : 0);
