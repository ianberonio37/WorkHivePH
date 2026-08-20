// prove_why_refused.mjs — the CM `why_refused` oracle: when the server says no, does the page say WHY?
//
// THIS ORACLE EXISTS BECAUSE THE PLATFORM HAS ALREADY SHIPPED ITS FAILURE, in both directions:
//   · a 42501 permission error rendered as "your session has expired", sending a signed-IN person to
//     re-authenticate for a problem authentication cannot fix (feedback_42501_told_a_signed_in_buyer_to_sign_in)
//   · 401 and 403 collapsed into one message, so neither audience got a true statement
//     (feedback_401_and_403_are_not_the_same_event)
// So the pass condition is NOT "some message appeared". It is: the refusal names PERMISSION rather than
// IDENTITY. A page that answers an injected 403 with "please sign in" is not merely vague — it is WRONG, in
// the direction that wastes the person's time.
//
// HOW THE REFUSAL IS INDUCED. A real PostgREST 403 body is returned for the page's own reads, patched at
// `window.fetch` — never `page.route`, because a warm service worker serves from cache and bypasses route
// interception (that is how an earlier failure probe measured nothing while reporting success). The body is
// the shape PostgREST actually sends for row-level-security refusal, so the client's error handling takes
// the same branch it would in production:
//     {"code":"42501","message":"permission denied for table …","details":null,"hint":null}
// Installed with addInitScript in a context closed after each page, so it cannot leak into another reading.
// NON-WRITING: it makes a READ return 403. Nothing is typed or submitted.
//
// THREE OUTCOMES:
//   PASS      — the page shows text that names permission/role/access (optionally alongside a generic line).
//   FAIL-WRONG— the page blames IDENTITY (sign in / session expired) for a permission refusal. The shipped bug.
//   FAIL-VAGUE— only a generic error ("something went wrong", "failed"), or nothing at all: the person is told
//               that it broke, never that they are not allowed, so they cannot act.
//
// THE CONTROL: the same page is read WITHOUT the injection first. If its normal text already matches the
// refusal vocabulary, this page cannot be graded — the signal has to APPEAR, or a page whose ordinary copy
// happens to contain "cannot" would pass for free. That is the same delta discipline the session-died oracle
// needed after public-feed's permanent "Sign In" CTA scored as a pass.
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
import { signIn, assertSignedIn } from './live_page_journeys.mjs';
import { SIGNED_OUT_SRC, REFUSAL_SRC, GENERIC_ERROR_SRC } from './session_signals.mjs';

const ORIGIN = process.env.WH_ORIGIN || 'http://127.0.0.1:5000';
const PAGES = ['hive', 'logbook', 'inventory', 'pm-scheduler', 'project-manager', 'dayplanner',
  'asset-hub', 'analytics', 'alert-hub', 'skillmatrix', 'shift-brain', 'voice-journal',
  'community', 'achievements', 'resume', 'report-sender', 'project-report',
  // ★FIVE PAGES WERE MISSING FROM THIS ROSTER, which is a coverage gap that reads as coverage: the
  // prover reported "17 of 17 graded, 0 failing" while index, public-feed, assistant, engineering-design
  // and analytics-report had never been asked. A roster is a claim about scope, and an incomplete one
  // makes a green look total. index and public-feed matter most here - public-feed is the ANON surface,
  // where confusing a permission refusal with being signed out is the easiest mistake to make.
  'index', 'public-feed', 'assistant', 'engineering-design', 'analytics-report'];
const args = process.argv.slice(2);
const GATE = args.includes('--gate');
const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();

// Patch fetch to answer every Supabase REST/RPC read with a PostgREST-shaped RLS refusal.
// COUNTS ITS OWN HITS, and uses `includes` rather than a regex — both because of the same failure.
// The first version tested the URL with a regex written inside a template literal, and the escaping
// collapsed: the file held `/\/rest\/v1\//`, which emits `/\/rest\/v1\//` — a regex that TERMINATES
// at its second character. The whole init script was therefore a SyntaxError, never ran, and every read
// succeeded normally... while the prover reported "NOTHING appeared: the reads were all refused and the page
// said nothing new at all" and blamed the page. A silently-inert injection is the vacuous-measurement class:
// the probe changed nothing and then judged the result.
// So: no regex (a plain substring cannot be mis-escaped), and `window.__whRefusalHits` is incremented on
// every intercepted call so the prover can REFUSE TO GRADE a page where the injection did not fire.
const INJECT = `(() => {
  window.__whRefusalHits = 0;
  const of = window.fetch;
  window.fetch = function (u, o) {
    const s = typeof u === 'string' ? u : (u && u.url) || '';
    if (s.includes('/rest/v1/')) {
      window.__whRefusalHits++;
      return Promise.resolve(new Response(JSON.stringify({
        code: '42501',
        message: 'permission denied for table',
        details: null, hint: null,
      }), { status: 403, statusText: 'Forbidden',
            headers: { 'Content-Type': 'application/json' } }));
    }
    return of.apply(this, arguments);
  };
})()`;

const READ = ({ soSrc, refSrc, genSrc }) => {
  const SO = new RegExp(soSrc, 'i');
  const REF = new RegExp(refSrc, 'i');
  const GEN = new RegExp(genSrc, 'i');
  const txt = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
  // QUOTE A WINDOW AROUND THE MATCH, NOT THE START OF THE "SENTENCE" IT FELL IN. The first version split
  // on /(?<=[.!?])\s+/ and quoted the first 110 chars of each matching chunk — but a dashboard's chrome
  // is mostly labels with no terminal punctuation, so the split yields one enormous pseudo-sentence and
  // the quote showed its OPENING while the matched phrase sat 900 characters later. Six of the greens in
  // this sweep would have banked evidence like "Retry Live · refreshed on load · Based on your logbook…"
  // for a claim about a refusal message — a quote that does not contain the thing it is evidence for,
  // which is the "a claim must name what it rests on" class in miniature.
  // So: find the match itself and take a window centred on it, with the matched text marked. The `g` copy
  // is local to each call so no lastIndex leaks between the three vocabularies.
  const pick = (re) => {
    const g = new RegExp(re.source, 'gi');
    const out = [];
    let m;
    while ((m = g.exec(txt)) && out.length < 3) {
      const s = Math.max(0, m.index - 55);
      out.push((s ? '…' : '') + txt.slice(s, Math.min(txt.length, m.index + m[0].length + 85))
               + (m.index + m[0].length + 85 < txt.length ? '…' : ''));
      if (m.index === g.lastIndex) g.lastIndex++;   // zero-width guard
    }
    return out;
  };
  return { chars: txt.length,
           saysRefusal: REF.test(txt), refusalQuotes: pick(REF),
           saysSignedOut: SO.test(txt), signedOutQuotes: pick(SO),
           saysGeneric: GEN.test(txt), genericQuotes: pick(GEN),
           head: txt.slice(0, 200) };
};

const browser = await chromium.launch();
const results = [];
for (const p of (ONE ? [ONE.replace(/\.html$/, '')] : PAGES)) {
  const rec = { page: p };
  try {
    // ── CONTROL: the page's ordinary text, with no injection.
    const c0 = await browser.newContext({ viewport: { width: 390, height: 844 } });
    await assertSignedIn(signIn(c0, 'supervisor'));
    const p0 = await c0.newPage();
    await p0.goto(`${ORIGIN}/${p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await p0.waitForTimeout(3200);
    rec.before = await p0.evaluate(READ, { soSrc: SIGNED_OUT_SRC, refSrc: REFUSAL_SRC,
                                          genSrc: GENERIC_ERROR_SRC });
    await c0.close();

    // ── the refusal, injected.
    const c1 = await browser.newContext({ viewport: { width: 390, height: 844 } });
    await assertSignedIn(signIn(c1, 'supervisor'));
    await c1.addInitScript(INJECT);
    const p1 = await c1.newPage();
    await p1.goto(`${ORIGIN}/${p}.html`, { waitUntil: 'domcontentloaded', timeout: 25000 });
    await p1.waitForTimeout(4200);
    rec.landed = (p1.url().split('/').pop() || '').replace(/\.html.*$/, '');
    rec.after = await p1.evaluate(READ, { soSrc: SIGNED_OUT_SRC, refSrc: REFUSAL_SRC,
                                         genSrc: GENERIC_ERROR_SRC });
    rec.injectionHits = await p1.evaluate(() => window.__whRefusalHits ?? null);
    await c1.close();

    const b = rec.before, a = rec.after;
    // The signal must APPEAR. A page whose ordinary copy already says "cannot" cannot be graded on it.
    rec.newRefusal = a.saysRefusal && !b.saysRefusal;
    rec.newSignedOut = a.saysSignedOut && !b.saysSignedOut;
    rec.newGeneric = a.saysGeneric && !b.saysGeneric;

    // THE INJECTION MUST HAVE FIRED. Zero hits means no read was refused, so nothing about the page's
    // refusal handling was exercised and any verdict would be about the probe.
    if (!rec.injectionHits) {
      rec.verdict = `the 403 injection intercepted ${rec.injectionHits === null ? 'nothing (it never ran)'
        : '0 requests'} — no read was refused, so this page's refusal handling was never exercised`;
      rec.ok = null;
    } else if (a.chars < 300) {
      rec.verdict = `page rendered only ${a.chars} characters under the refusal — under-rendered, not graded`;
      rec.ok = null;
    } else if (b.saysRefusal) {
      rec.verdict = 'this page ALREADY says something matching the refusal vocabulary before any injection '
        + `(${(b.refusalQuotes[0] || '').slice(0, 60)}) — the signal cannot be attributed, so not graded`;
      rec.ok = null;
    } else if (rec.newSignedOut && !rec.newRefusal) {
      rec.verdict = 'BLAMES IDENTITY FOR A PERMISSION REFUSAL — a 42501 was answered with '
        + `"${(a.signedOutQuotes[0] || '').slice(0, 70)}". A signed-in person is sent to re-authenticate `
        + 'for something authentication cannot fix.';
      rec.ok = false;
    } else if (rec.newRefusal) {
      rec.verdict = `names the reason: "${(a.refusalQuotes[0] || '').slice(0, 80)}"`;
      rec.ok = true;
    } else if (rec.newGeneric) {
      rec.verdict = `only a GENERIC error appeared ("${(a.genericQuotes[0] || '').slice(0, 60)}") — the `
        + 'person is told it broke, never that they are not allowed';
      rec.ok = false;
    } else {
      rec.verdict = 'NOTHING appeared: the reads were all refused and the page said nothing new at all';
      rec.ok = false;
    }
  } catch (e) { rec.error = String(e.message || e).slice(0, 150); rec.ok = null; }
  results.push(rec);
  console.log(`  ${p.padEnd(20)} ${rec.ok === true ? 'PASS' : rec.ok === false ? 'FAIL' : 'UNGRADED'}  `
    + String(rec.verdict || rec.error || '').slice(0, 88));
}
await browser.close();

const graded = results.filter((r) => r.ok !== null);
const bad = graded.filter((r) => !r.ok);
writeFileSync('why_refused_report.json', JSON.stringify({
  injected: { status: 403, code: '42501' },
  totals: { pages: results.length, graded: graded.length,
            ungraded: results.filter((r) => r.ok === null).length, failing: bad.length },
  pages: results,
}, null, 1));
console.log('\n  wrote why_refused_report.json');
for (const u of results.filter((r) => r.ok === null)) {
  console.log(`    UNGRADED ${u.page} — ${(u.error || u.verdict || '').slice(0, 110)}`);
}
console.log(`  ${graded.length} of ${results.length} page(s) graded, ${bad.length} failing`);
if (!graded.length) {
  console.log('  FAIL — NOTHING WAS MEASURED. Zero failures over an empty denominator is not a pass.');
} else if (bad.length) {
  for (const r of bad) console.log(`  FAIL ${r.page}: ${r.verdict}`);
} else {
  console.log(`  PASS — all ${graded.length} page(s) answer a 42501 refusal by naming the reason, and none `
    + 'blames identity for a permission problem');
}
if (GATE) process.exit(bad.length || !graded.length ? 1 : 0);
