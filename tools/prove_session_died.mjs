// prove_session_died.mjs — the CO `session_died` oracle: when the session is gone, does the page SAY so?
//
// This is the failure this bank has already caught three separate times in other shapes, and it is
// always the same shape: a read that could not succeed renders as though it had, and the number it shows
// is legitimate-looking. `feedback_a_zero_that_was_never_a_fallback` — two moderation badges asserting
// "0 waiting" on a FAILED read. `feedback_42501_told_a_signed_in_buyer_to_sign_in` — the inverse, a
// permission error mislabelled as a dead session. `feedback_a_failed_read_offered_first_run_onboarding`
// — skillmatrix asking a worker to re-pick a discipline, overwriting what they had. In every one the
// page was confident and wrong.
//
// So the oracle is NOT "does it redirect to sign-in". Several of these pages are legitimately readable
// signed-out (public-feed, engineering-design, index), and a redirect is only one honest answer. The
// oracle is: **the page must not present a signed-out state as though it were signed-in data.** It has
// to do ONE of three honest things, and the prover accepts all three and NAMES which:
//   1. REDIRECT to a sign-in surface, or render a sign-in / session-expired prompt.
//   2. Render an explicit signed-out / empty-with-a-reason state that a person can read as such.
//   3. Be a genuinely public surface that renders the SAME public content signed-out as signed-in.
// What FAILS is the fourth behaviour: hive-scoped numbers still rendered, or zeros/dashes with no
// explanation, as if the absence of data were the data.
//
// HOW THE SESSION IS KILLED, and why not just `context.clearCookies()`: supabase-js persists the session
// in localStorage under `sb-<ref>-auth-token`, not a cookie, so clearing cookies leaves the page signed
// in and the whole probe measures nothing. The token is removed from localStorage AND sessionStorage,
// every `sb-*` key is swept (the key is project-ref-dependent and hardcoding one ref is how this goes
// silently vacuous), and then the page is RELOADED so the client re-reads storage from cold.
//
// THE NON-VACUITY CONTROL, which is what makes a pass mean anything: the SAME page is measured signed-in
// FIRST, and the signed-in reading must differ from the signed-out one. If a page looks identical either
// way it is either genuinely public (recorded as case 3, with its content compared) or the kill did not
// work — and those two must never be confused. A probe that cannot prove it changed anything cannot
// report that the change was handled correctly.
//
// NON-WRITING: it reads, clears client-side storage, and reloads. It submits nothing. Clearing storage
// touches only this browser context, never the shared database.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { SIGNED_OUT_SRC, REASONED_EMPTY_SRC } from './session_signals.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const PAGES = ['index', 'hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager',
  'dayplanner', 'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain',
  'voice-journal', 'assistant', 'community', 'public-feed', 'achievements',
  'engineering-design', 'resume', 'report-sender', 'project-report', 'analytics-report'];
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// NOTE: these regexes are declared INSIDE the browser function below, not out here. A page.evaluate
// callback is serialized and run in the page, where a Node-scope constant does not exist — referencing
// one throws `ReferenceError: SAYS_SIGNED_OUT is not defined` and the page comes back UNGRADED, which
// (before the fix below) the summary then reported as a PASS.
const READ = ({ soSrc, reSrc }) => {
  // "you are not signed in / your session ended" — an HONEST answer.
  // WIDENED 2026-08-13, after the SAME too-narrow vocabulary in the V2/V3 prover reported analytics as
  // silently empty when it actually renders "Authentication required" and "Analytics unavailable".
  // Ported here so V1 and V2/V3 judge by the same words — otherwise one level would keep a finding
  // the other had already withdrawn, and the bank would hold two contradictory readings of one page.
  const SAYS_SIGNED_OUT = new RegExp(soSrc, 'i');
  // "there is nothing here, and here is why" — also honest.
  const SAYS_REASONED_EMPTY = new RegExp(reSrc, 'i');
  const txt = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
  // Numbers a person would read as hive data. Deliberately leaf-scoped and deduped by class, because
  // counting every ancestor that CONTAINS a number inflates this several-fold.
  const nums = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.children.length) continue;
    const t = (el.textContent || '').trim();
    if (!/^[₱$]?\s*\d[\d,.]*\s*%?$/.test(t)) continue;
    const s = getComputedStyle(el); const b = el.getBoundingClientRect();
    if (s.display === 'none' || s.visibility === 'hidden' || b.height <= 0) continue;
    nums.push({ t, cls: String(el.className || '').slice(0, 30) });
  }
  const nonZero = nums.filter((n) => /[1-9]/.test(n.t));
  return {
    chars: txt.length,
    head: txt.slice(0, 260),
    nums: nums.length,
    nonZero: nonZero.length,
    nonZeroSample: nonZero.slice(0, 6).map((n) => `${n.t}${n.cls ? ' .' + n.cls : ''}`),
    // The FULL list, text + class, because the leak test intersects the two readings and a truncated
    // sample would silently narrow the denominator it compares against.
    nonZeroAll: nonZero.map((n) => ({ t: n.t, cls: n.cls })),
    saysSignedOut: SAYS_SIGNED_OUT.test(txt),
    saysReasonedEmpty: SAYS_REASONED_EMPTY.test(txt),
    // A sign-in FORM is the strongest possible honest answer.
    hasAuthForm: !!document.querySelector('input[type="password"]'),
  };
};

const KILL = () => {
  const killed = [];
  for (const store of [localStorage, sessionStorage]) {
    for (const k of Object.keys(store)) {
      if (/^sb-|auth-token|supabase/i.test(k)) { killed.push(k); store.removeItem(k); }
    }
  }
  return killed;
};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await assertSignedIn(signIn(ctx, 'supervisor'));
const page = await ctx.newPage();

const results = [];
for (const p of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  const rec = { page: p };
  try {
    // ── signed-in baseline (the control): what does this page look like WITH a session?
    await page.goto(`${ORIGIN}/${p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(3000);
    rec.landedIn = (page.url().split('/').pop() || '').replace(/\.html.*$/, '');
    rec.before = await page.evaluate(READ, { soSrc: SIGNED_OUT_SRC, reSrc: REASONED_EMPTY_SRC });

    // ── kill the session and re-read from cold
    rec.killedKeys = await page.evaluate(KILL);
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 25000 });
    await page.waitForTimeout(3400);
    rec.landedOut = (page.url().split('/').pop() || '').replace(/\.html.*$/, '');
    rec.after = await page.evaluate(READ, { soSrc: SIGNED_OUT_SRC, reSrc: REASONED_EMPTY_SRC });

    // A PAGE STILL LOADING IS NOT A PAGE THAT FAILED TO EXPLAIN ITSELF. First full sweep reported
    // asset-hub and analytics as UNEXPLAINED EMPTY with ZERO numbers on screen — and zero numbers is
    // equally the signature of a page that simply had not finished rendering 3.4s after a reload. That
    // is the SLOW-vs-STUCK distinction `prove_component_states.mjs` already had to learn: reporting a
    // slow page as a broken one is a fabricated defect. So before anything is called a failure, a page
    // that looks under-rendered or is still showing loading affordances gets another 6 seconds and is
    // re-read; if it is STILL not settled the row is UNGRADED, never failed, because the reading cannot
    // distinguish the two.
    // ONLY *VISIBLE* BUSY ELEMENTS COUNT. Counting them by selector alone made this guard too blunt and
    // it immediately disqualified a page that was plainly finished: `public-feed` flipped from a correct
    // PASS to UNGRADED on 1 busy element at 2473 rendered characters, because pages routinely leave a
    // skeleton node in the DOM with `display:none` after the real content arrives. A hidden skeleton is
    // not a loading state — it is a template. Same visibility discipline the stuck-skeleton oracle needed.
    const settled = () => page.evaluate(() => {
      let busy = 0;
      for (const el of document.querySelectorAll(
        '[aria-busy="true"],.skeleton,.wh-skeleton,.animate-pulse,.spinner,.loading')) {
        const s = getComputedStyle(el); const b = el.getBoundingClientRect();
        if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity <= 0.01) continue;
        if (b.width <= 0 || b.height <= 0) continue;
        busy++;
      }
      return { busy, chars: (document.body.innerText || '').trim().length };
    });
    let s = await settled();
    if (s.busy > 0 || s.chars < 400) {
      await page.waitForTimeout(6000);
      const s2 = await settled();
      rec.readiness = { first: s, second: s2 };
      if (s2.busy > 0 || s2.chars < 400) {
        rec.verdict = `UNDER-RENDERED after +6s (${s2.busy} busy/skeleton element(s), `
          + `${s2.chars} chars) — a page that has not finished is not a page that failed to explain `
          + 'itself, so this is not graded';
        rec.ok = null;
        rec.after = await page.evaluate(READ, { soSrc: SIGNED_OUT_SRC, reSrc: REASONED_EMPTY_SRC });
        results.push(rec);
        console.log(`  ${p.padEnd(20)} UNGRADED  killed=${rec.killedKeys.length}  ${rec.verdict}`
          .slice(0, 118));
        await assertSignedIn(signIn(ctx, 'supervisor'));
        continue;
      }
      rec.after = await page.evaluate(READ, { soSrc: SIGNED_OUT_SRC, reSrc: REASONED_EMPTY_SRC });      // settled on the retry — re-read before grading
    }

    const a = rec.after, b = rec.before;
    rec.redirected = rec.landedOut !== rec.landedIn;
    rec.changed = rec.redirected || a.chars !== b.chars || a.nonZero !== b.nonZero;

    // THE SIGNED-OUT SIGNAL MUST BE A DELTA, NOT FURNITURE. First cut credited `public-feed` with
    // `says-signed-out` — but its text matched the phrase BEFORE the kill too: the page permanently
    // renders "Sign In →" and "Sign in to join the conversation" as its read-only CTA, signed in or
    // out, and the body was byte-identical either way (2438 → 2438 chars, 0 non-zero values both
    // times). A body-wide keyword match had read the page's own marketing copy as evidence that it
    // handled a dead session. So a sentence only counts if it APPEARED, and the unchanged/public case
    // is now tested BEFORE any text match rather than after it.
    rec.newAuthForm = a.hasAuthForm && !b.hasAuthForm;
    rec.newSignedOutText = a.saysSignedOut && !b.saysSignedOut;
    // Signed-in values still on screen after the session is gone, matched on text AND class.
    // A SURVIVOR NEEDS AN IDENTITY AND A NON-TRIVIAL VALUE, or this test invents leaks. The first cut
    // matched on `text|class` alone and reported `index` as leaking one value: a bare "3" with NO class.
    // A single digit in an unclassed element appears in step indicators, list positions and marketing
    // copy on almost every page, so "3" surviving a swap from the dashboard to the landing page is a
    // coincidence, not hive data outliving its session. A leak claim now requires the element to carry a
    // class (an identity that ties the number to a component) and the value to be more than one digit —
    // multi-digit, currency or percent. A genuinely leaked KPI is `1,240 .oh-tile-num`, never a bare 3.
    const idable = (n) => n.cls && (n.t.length > 1);
    const key = (n) => `${n.t}|${n.cls}`;
    const bset = new Set((b.nonZeroAll || []).filter(idable).map(key));
    rec.survivors = (a.nonZeroAll || []).filter(idable).filter((n) => bset.has(key(n)))
      .map((n) => `${n.t} .${n.cls}`);

    if (!rec.killedKeys.length) {
      // Nothing to kill. Either the page never had a session (a public surface reached signed-out
      // anyway) or the storage key moved. Both are UNGRADED — never a pass.
      rec.verdict = 'no-session-to-kill'; rec.ok = null;
    // THE SURVIVOR LIST IS RECORDED, NOT GATED — because it cannot tell leaked USER data from static
    // FURNITURE, and two runs proved it in both directions. It called `index` a leak on a bare "3" with
    // no class (a coincidence between a step indicator and a tile), and it called `achievements` a leak
    // on 18/38/63/83 `.wh-avatar-lvl` — the Iron/Bronze/Silver/Gold tier THRESHOLDS, which are identical
    // for every user and SHOULD survive a signed-out reload. Distinguishing the two needs to know which
    // numbers are user-scoped, which no generic DOM read can answer; claiming it anyway would be
    // manufacturing findings. So this oracle grades ONLY the classification it can actually establish —
    // did the page respond to the missing session at all — and the survivor list travels with the row as
    // context for a human, never as a verdict.
    } else if (rec.redirected) {
      rec.verdict = 'redirected-to-' + rec.landedOut; rec.ok = true;
    } else if (rec.newAuthForm) {
      rec.verdict = 'renders-a-sign-in-form-it-did-not-render-before'; rec.ok = true;
    } else if (rec.newSignedOutText) {
      rec.verdict = 'swapped-to-a-signed-out-view-that-says-so'; rec.ok = true;
    } else if (a.saysReasonedEmpty) {
      rec.verdict = 'empty-with-a-stated-reason'; rec.ok = true;
    } else if (b.nonZero === 0) {
      // THE ORACLE'S SUBJECT IS DATA THAT COULD MISLEAD, AND THIS PAGE NEVER SHOWED ANY. `assistant`
      // and `report-sender` rendered ZERO non-zero values even WITH a session — a chat thread and an
      // empty report list — so there is no figure here that a dead session could turn into a false
      // reassurance. Failing them would be claiming a defect in the absence of the thing the claim is
      // about. Recorded UNGRADED with that reason so it stays owed rather than being banked either way.
      rec.verdict = 'no-data-signed-in-either (0 non-zero values WITH a session), so this view has no '
        + 'figure a dead session could misrepresent — not gradable by this oracle';
      rec.ok = null;
    } else if (!rec.changed) {
      // Identical with a session and without one, and no honest signal appeared. Either the kill did not
      // take or this view never reflected the session. UNGRADED either way — an earlier version called
      // this `public-surface-identical-signed-out` and PASSED it, which labelled `project-report` (a hive
      // report page) a public surface purely because it renders no figures in either state. A verdict must
      // not name a mechanism it did not establish. CHECKED AFTER the no-data branch, because when both
      // apply the accurate reason is "this view has no figures", not "identical with data present" — the
      // first ordering printed the latter for public-feed and project-report, which have none. Nothing was
      // mis-banked (both are UNGRADED), but a recorded reason that contradicts its own reading is the same
      // defect as a verdict that does, and these reasons are what the roadmap reads later.
      rec.verdict = 'IDENTICAL either way with figures present — cannot distinguish a public surface from '
        + 'a kill that did not take, so not graded';
      rec.ok = null;
    } else {
      // WORDED NARROWLY, because the obvious wording over-claims. "no sentence telling the person their
      // session ended" assumes the page OUGHT to announce an ended session — but index.html:3520 shows
      // this platform deliberately supports "has a name, no auth session" as a GUEST WORKER and shows an
      // upgrade nudge, so a cached identity here is a designed state, not a bug. What is NOT defensible
      // is the other half: hive-scoped reads that could not have succeeded rendering as zeros with no
      // word that anything failed. On index that surfaces as "✓ ALL CLEAR · Nothing urgent right now" —
      // an affirmative safety claim derived from a read that did not happen.
      // The verdict states what was actually counted. An earlier wording said "N number(s), all
      // zero/blank" on every page reaching this branch, which flatly contradicted the reading on
      // `achievements` — 6 of its 9 numbers were non-zero (the static tier thresholds). A verdict that
      // misdescribes its own measurement is the same defect class as a mislabelled metric.
      rec.verdict = a.nonZero > 0
        ? `UNEXPLAINED — still renders ${a.nonZero} of ${a.nums} number(s) non-zero `
          + `(${rec.survivors.length} of them also present signed-in, which may be static furniture: `
          + `${rec.survivors.slice(0, 3).join('; ') || 'none'}) and nothing on screen says the data `
          + 'could not be loaded'
        : `UNEXPLAINED EMPTY — ${a.nums} number(s), all zero/blank, and nothing on screen says the `
          + 'data could not be loaded';
      rec.ok = false;
    }
  } catch (e) { rec.error = String(e).slice(0, 150); rec.ok = null; }
  console.log(`  ${p.padEnd(20)} ${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : 'UNGRADED'}`
    + `  killed=${(rec.killedKeys || []).length}`
    + `  in:${rec.before ? rec.before.nonZero : '?'}nz -> out:${rec.after ? rec.after.nonZero : '?'}nz`
    + `  ${rec.verdict || rec.error || ''}`.slice(0, 78));
  results.push(rec);
  // Re-establish the session for the next page — the kill is per-context and would otherwise make
  // every subsequent baseline a signed-out one, quietly turning the whole sweep vacuous.
  await assertSignedIn(signIn(ctx, 'supervisor'));
}
await browser.close();

const graded = results.filter((r) => r.ok !== null);
const bad = graded.filter((r) => !r.ok);
writeFileSync('session_died_report.json', JSON.stringify({
  origin: ORIGIN, view: 'V1',
  totals: { pages: results.length, graded: graded.length,
            ungraded: results.filter((r) => r.ok === null).length, failing: bad.length },
  pages: results,
}, null, 1));
// ZERO FAILURES OVER ZERO MEASUREMENTS IS NOT A PASS. The first run of this file proved the point on
// itself: a ReferenceError left every page UNGRADED and the summary printed "PASS — no page presents a
// dead session as signed-in data", which is true only in the sense that no page was looked at. An empty
// denominator has to be LOUDER than a failure, not quieter, because a failure gets triaged and a
// vacuous green gets banked.
const ungraded = results.filter((r) => r.ok === null);
console.log('\n  wrote session_died_report.json');
console.log(`  ${graded.length} graded, ${bad.length} failing, ${ungraded.length} ungraded`);
for (const u of ungraded) {
  console.log(`    UNGRADED ${u.page.padEnd(20)} ${u.error || u.verdict || 'no reason recorded'}`
    .slice(0, 150));
}
const vacuous = graded.length === 0;
if (vacuous) {
  console.log(`  FAIL — NOTHING WAS MEASURED (0 of ${results.length} page(s) graded). Zero failures `
    + 'over an empty denominator is not a pass.');
} else if (bad.length) {
  console.log('  FAIL — ' + bad.map((r) => `${r.page} (${r.verdict})`).join('; '));
} else {
  console.log(`  PASS — ${graded.length} page(s) measured, none presents a dead session as signed-in `
    + `data${ungraded.length ? ` (${ungraded.length} ungraded and listed above, NOT counted)` : ''}`);
}
if (GATE) process.exit(bad.length || vacuous ? 1 : 0);
